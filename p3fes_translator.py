#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import shutil
from datetime import datetime
from deep_translator import GoogleTranslator
import requests
import time
import re
import sys
import subprocess
from dotenv import load_dotenv
from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer
import struct
import mimetypes
from collections import defaultdict, Counter

# Chargement des variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('translation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class SpecialTokens:
    """Gestion des tokens spéciaux pour Persona 3 FES."""
    
    # Tokens de formatage du jeu (codes de contrôle)
    GAME_FORMAT_TOKENS = {
        # Codes de formatage de texte
        r'\{F[0-9A-F]{2}\s+[0-9A-F]{2}\s+[0-9A-F]{2}\s+[0-9A-F]{2}\}': 'GAME_FORMAT_1',  # {F2 08 FF FF}
        r'\{F[0-9A-F]{2}\s+[0-9A-F]{2}\}': 'GAME_FORMAT_2',  # {F1 3F}
        r'\{[0-9A-F]{2}\}': 'GAME_FORMAT_3',  # {0A}
        r'\{00\}': 'GAME_END',  # Fin de message
        
        # Codes de dialogue et d'interface
        r'\{NAME\d+\}': 'PLAYER_NAME',  # Nom du joueur
        r'\{ITEM\d+\}': 'ITEM_NAME',  # Nom d'objet
        r'\{PERSONA\d+\}': 'PERSONA_NAME',  # Nom de Persona
        r'\{SKILL\d+\}': 'SKILL_NAME',  # Nom de compétence
        r'\{LOCATION\d+\}': 'LOCATION_NAME',  # Nom de lieu
        
        # Codes de formatage avancés
        r'\{COLOR\d+\}': 'TEXT_COLOR',  # Couleur du texte
        r'\{SPEED\d+\}': 'TEXT_SPEED',  # Vitesse d'affichage
        r'\{WAIT\d+\}': 'TEXT_WAIT',  # Pause dans le texte
        r'\{CLEAR\}': 'CLEAR_TEXT',  # Effacer le texte
        r'\{WINDOW\d+\}': 'WINDOW_TYPE',  # Type de fenêtre
        
        # Codes de son et d'animation
        r'\{SOUND\d+\}': 'SOUND_EFFECT',  # Effet sonore
        r'\{VOICE\d+\}': 'VOICE_LINE',  # Ligne vocale
        r'\{ANIM\d+\}': 'ANIMATION',  # Animation
        r'\{FACE\d+\}': 'FACE_EMOTION',  # Expression faciale
        
        # Codes de menu et de choix
        r'\{CHOICE\d+\}': 'MENU_CHOICE',  # Option de menu
        r'\{YESNO\}': 'YES_NO_PROMPT',  # Prompt Oui/Non
        r'\{INPUT\}': 'TEXT_INPUT',  # Saisie de texte
        r'\{CURSOR\d+\}': 'CURSOR_POS',  # Position du curseur
        
        # Codes de statut et de combat
        r'\{HP\d+\}': 'HP_VALUE',  # Points de vie
        r'\{SP\d+\}': 'SP_VALUE',  # Points de magie
        r'\{STATUS\d+\}': 'STATUS_EFFECT',  # Effet de statut
        r'\{DAMAGE\d+\}': 'DAMAGE_VALUE',  # Valeur de dégâts
    }
    
    # Tokens de formatage standard
    FORMAT_TOKENS = {
        '\n': 'NEWLINE',
        '\t': 'TAB',
        '\r': 'CARRIAGE_RETURN',
        '\\n': 'NEWLINE_ESC',
        '\\t': 'TAB_ESC',
        '\\r': 'CARRIAGE_RETURN_ESC',
        '「': 'DIALOG_START',  # Guillemets japonais pour dialogue
        '」': 'DIALOG_END',
        '『': 'THOUGHT_START',  # Guillemets japonais pour pensées
        '』': 'THOUGHT_END'
    }
    
    # Tokens de commande
    COMMAND_TOKENS = {
        'MSG_': 'MESSAGE_ID',
        'CMD_': 'COMMAND_ID',
        'EVT_': 'EVENT_ID',
        'SCENE_': 'SCENE_ID',
        'BATTLE_': 'BATTLE_ID',
        'QUEST_': 'QUEST_ID'
    }
    
    @staticmethod
    def extract_game_tokens(text: str) -> tuple:
        """
        Extrait les tokens de formatage du jeu et le texte à traduire.
        Retourne un tuple (tokens, texte_clean).
        """
        tokens = []
        clean_text = text
        
        # Extraction des tokens de formatage du jeu
        for pattern, token_type in SpecialTokens.GAME_FORMAT_TOKENS.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                token = match.group(0)
                # Stocke le token avec sa position et son type
                tokens.append({
                    'token': token,
                    'type': token_type,
                    'position': match.start(),
                    'length': len(token)
                })
                # Remplace le token par un espace pour préserver la longueur
                clean_text = clean_text[:match.start()] + ' ' * len(token) + clean_text[match.end():]
        
        # Nettoyage des espaces multiples tout en préservant la structure
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return tokens, clean_text
    
    @staticmethod
    def reconstruct_text(clean_text: str, tokens: list) -> str:
        """
        Reconstruit le texte original avec les tokens de formatage.
        Préserve la structure et le formatage original.
        """
        # Trie les tokens par position décroissante pour ne pas perturber les indices
        sorted_tokens = sorted(tokens, key=lambda x: x['position'], reverse=True)
        
        result = clean_text
        for token_info in sorted_tokens:
            # Insère le token à sa position originale
            pos = token_info['position']
            result = result[:pos] + token_info['token'] + result[pos:]
        
        return result
    
    @staticmethod
    def is_special_token(text: str) -> bool:
        """Vérifie si le texte contient des tokens spéciaux."""
        # Vérifie les tokens de formatage du jeu
        if any(re.search(pattern, text) for pattern in SpecialTokens.GAME_FORMAT_TOKENS.keys()):
            return True
            
        # Vérifie les tokens de formatage standard
        if any(token in text for token in SpecialTokens.FORMAT_TOKENS):
            return True
            
        # Vérifie les tokens de commande
        if any(text.startswith(token) for token in SpecialTokens.COMMAND_TOKENS):
            return True
            
        return False
    
    @staticmethod
    def preserve_special_tokens(original_text: str, translated_text: str) -> str:
        """Préserve les tokens spéciaux dans le texte traduit."""
        # Extraction des tokens du texte original
        tokens, clean_original = SpecialTokens.extract_game_tokens(original_text)
        
        # Si le texte original ne contient que des tokens spéciaux
        if not clean_original.strip():
            return original_text
            
        # Nettoyage du texte traduit
        clean_translated = translated_text.strip()
        
        # Reconstruction du texte avec les tokens originaux
        return SpecialTokens.reconstruct_text(clean_translated, tokens)

class FileAnalyzer:
    """Analyseur automatique de fichiers pour détecter le contenu traduisible."""
    
    def __init__(self):
        self.magic_signatures = {
            # Signatures de fichiers de jeu courants
            b'PM1\x00': 'pm1_format',
            b'PAC\x00': 'pac_format', 
            b'PAK\x00': 'pak_format',
            b'BF\x00\x00': 'bf_format',
            b'TBL\x00': 'tbl_format',
            
            # Signatures génériques
            b'RIFF': 'riff_format',
            b'\x89PNG': 'png_image',
            b'MZ': 'executable',
            b'\x7fELF': 'elf_executable',
            
            # Archives
            b'PK\x03\x04': 'zip_archive',
            b'Rar!': 'rar_archive',
            
            # Formats de texte
            b'\xff\xfe': 'utf16_le_text',
            b'\xfe\xff': 'utf16_be_text',
            b'\xef\xbb\xbf': 'utf8_bom_text',
        }
        
        self.text_indicators = [
            # Mots courants en anglais dans les jeux
            br'[Ss]tart',
            br'[Pp]ress',
            br'[Gg]ame\s+[Oo]ver',
            br'[Ll]oading',
            br'[Cc]ontinue',
            br'[Nn]ew\s+[Gg]ame',
            br'[Ss]ave',
            br'[Ll]oad',
            br'[Qq]uit',
            br'[Ee]xit',
            br'[Oo]ptions',
            br'[Ss]ettings',
            br'[Vv]olume',
            br'[Hh]elp',
            br'[Yy]es',
            br'[Nn]o',
            br'[Oo][Kk]',
            br'[Cc]ancel',
            
            # Textes spécifiques à Persona
            br'[Pp]ersona',
            br'[Tt]artarus',
            br'SEES',
            br'[Ee]voker',
            br'[Ss]hadow',
            br'[Aa]rcana',
            br'[Cc]ompendium',
            br'[Vv]elvet\s+[Rr]oom',
        ]
        
        self.analysis_results = {}
    
    def detect_translation_status(self, file_path: Path) -> Dict:
        """
        Détecte si un fichier a déjà été traduit et son niveau de traduction.
        Retourne des informations sur le statut de traduction.
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            if len(data) == 0:
                return {'status': 'empty', 'confidence': 0.0, 'indicators': []}
            
            # Convertir en texte pour analyse
            text_content = ""
            for encoding in ['utf-8', 'ascii', 'latin1', 'shift_jis']:
                try:
                    text_content = data.decode(encoding, errors='ignore')
                    break
                except:
                    continue
            
            # Indicateurs de traduction française
            french_indicators = [
                # Mots français courants dans les jeux
                r'\b(?:bonjour|salut|bienvenue|merci|oui|non|annuler|continuer|quitter)\b',
                r'\b(?:jeu|partie|joueur|démarrer|charger|sauvegarder|options)\b',
                r'\b(?:nouveau|ancien|précédent|suivant|retour|aide|fin)\b',
                r'\b(?:appuyez|pressez|cliquez|sélectionnez|choisissez)\b',
                
                # Indicateurs spécifiques aux traductions automatiques
                r'\b(?:chargement|chargeme|nouvea|annu|gibier|voit)\b',  # Textes tronqués typiques
                r'\.\.\.+',  # Points de suspension multiples (troncature)
                
                # Accents et caractères français
                r'[àâäéèêëïîôöùûüÿç]',
                
                # Expressions françaises de jeu
                r'(?:fin de partie|game over traduit|partie terminée)',
                r'(?:essayer à nouveau|réessayer)',
                r'(?:visitez|vérifiez|utilisez)',
            ]
            
            # Indicateurs anglais (pour détecter les non-traduits)
            english_indicators = [
                r'\b(?:start|press|game\s+over|loading|new\s+game|continue|quit|yes|no|ok|cancel)\b',
                r'\b(?:welcome|hello|thanks|help|options|settings|save|load)\b',
                r'\b(?:try\s+again|game\s+over|press\s+any\s+key)\b',
            ]
            
            # Compter les occurrences
            french_count = 0
            english_count = 0
            translation_indicators = []
            
            text_lower = text_content.lower()
            
            for pattern in french_indicators:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    french_count += len(matches)
                    translation_indicators.extend([f"French: {match}" for match in matches[:3]])  # Limiter les exemples
            
            for pattern in english_indicators:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    english_count += len(matches)
            
            # Calculer le score de traduction
            total_indicators = french_count + english_count
            if total_indicators == 0:
                translation_ratio = 0.0
                status = 'no_text'
            else:
                translation_ratio = french_count / total_indicators
                if translation_ratio >= 0.7:
                    status = 'fully_translated'
                elif translation_ratio >= 0.3:
                    status = 'partially_translated'
                elif english_count > 0:
                    status = 'not_translated'
                else:
                    status = 'unknown'
            
            return {
                'status': status,
                'confidence': translation_ratio,
                'french_indicators': french_count,
                'english_indicators': english_count,
                'indicators': translation_indicators[:5],  # Top 5 exemples
                'total_indicators': total_indicators
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'confidence': 0.0,
                'indicators': [f"Error: {str(e)}"],
                'error': str(e)
            }
    
    def detect_file_format(self, file_path: Path) -> Tuple[str, float]:
        """
        Détecte le format d'un fichier et sa probabilité de contenir du texte.
        Retourne (format_detecté, score_de_confiance)
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(512)  # Lire les premiers 512 bytes
                
            if not header:
                return 'empty_file', 0.0
            
            # Vérification des signatures magiques
            detected_format = 'unknown'
            for signature, format_name in self.magic_signatures.items():
                if header.startswith(signature):
                    detected_format = format_name
                    break
            
            # Score basé sur la présence de texte lisible
            text_score = self._calculate_text_score(header)
            
            # Bonus pour les formats de jeu connus
            format_bonus = 0.0
            if detected_format in ['pm1_format', 'pac_format', 'pak_format', 'bf_format', 'tbl_format']:
                format_bonus = 0.3
            elif 'text' in detected_format:
                format_bonus = 0.5
            
            final_score = min(1.0, text_score + format_bonus)
            
            return detected_format, final_score
            
        except Exception as e:
            logging.debug(f"Erreur d'analyse de {file_path}: {e}")
            return 'error', 0.0
    
    def _calculate_text_score(self, data: bytes) -> float:
        """Calcule un score de probabilité de présence de texte."""
        if len(data) == 0:
            return 0.0
        
        # Compteur de caractères imprimables
        printable_count = 0
        for byte in data:
            if 32 <= byte <= 126 or byte in [9, 10, 13]:  # ASCII imprimable + TAB/LF/CR
                printable_count += 1
        
        printable_ratio = printable_count / len(data)
        
        # Recherche de mots indicateurs
        indicator_score = 0.0
        for pattern in self.text_indicators:
            if re.search(pattern, data, re.IGNORECASE):
                indicator_score += 0.1
        
        # Score final
        text_score = (printable_ratio * 0.7) + min(indicator_score, 0.3)
        
        return text_score
    
    def analyze_directory(self, directory: Path, max_files: int = None) -> Dict:
        """
        Analyse tous les fichiers d'un répertoire et retourne un rapport.
        """
        analysis_report = {
            'total_files': 0,
            'analyzed_files': 0,
            'promising_files': [],
            'translated_files': [],
            'untranslated_files': [],
            'partially_translated_files': [],
            'by_format': defaultdict(list),
            'by_score': defaultdict(list),
            'by_translation_status': defaultdict(list),
            'errors': [],
            'recommendations': [],
            'translation_summary': {
                'fully_translated': 0,
                'partially_translated': 0,
                'not_translated': 0,
                'no_text': 0,
                'unknown': 0,
                'error': 0
            },
            'ignored_files': 0
        }
        
        all_files = []
        ignored_count = 0
        
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = Path(root) / file
                if file_path.is_file():
                    # Ignorer les fichiers .backup
                    if file_path.suffix.lower() == '.backup' or '.backup' in file_path.name:
                        ignored_count += 1
                        continue
                    all_files.append(file_path)
        
        analysis_report['total_files'] = len(all_files)
        analysis_report['ignored_files'] = ignored_count
        
        # Limiter si demandé
        if max_files and len(all_files) > max_files:
            all_files = all_files[:max_files]
            analysis_report['note'] = f"Analyse limitée aux {max_files} premiers fichiers"
        
        for file_path in all_files:
            try:
                file_format, score = self.detect_file_format(file_path)
                translation_status = self.detect_translation_status(file_path)
                
                file_info = {
                    'path': str(file_path),
                    'name': file_path.name,
                    'size': file_path.stat().st_size,
                    'format': file_format,
                    'text_score': score,
                    'extension': file_path.suffix.lower(),
                    'translation_status': translation_status['status'],
                    'translation_confidence': translation_status['confidence'],
                    'french_indicators': translation_status.get('french_indicators', 0),
                    'english_indicators': translation_status.get('english_indicators', 0),
                    'translation_examples': translation_status.get('indicators', [])
                }
                
                analysis_report['by_format'][file_format].append(file_info)
                analysis_report['analyzed_files'] += 1
                
                # Classer par statut de traduction
                status = translation_status['status']
                analysis_report['by_translation_status'][status].append(file_info)
                analysis_report['translation_summary'][status] += 1
                
                # Classer par score
                if score >= 0.7:
                    analysis_report['by_score']['high'].append(file_info)
                    # Ne considérer comme prometteur que s'il n'est pas déjà traduit
                    if status not in ['fully_translated']:
                        analysis_report['promising_files'].append(file_info)
                        analysis_report['untranslated_files'].append(file_info)
                    elif status == 'fully_translated':
                        analysis_report['translated_files'].append(file_info)
                elif score >= 0.4:
                    analysis_report['by_score']['medium'].append(file_info)
                    if status not in ['fully_translated']:
                        analysis_report['promising_files'].append(file_info)
                        analysis_report['untranslated_files'].append(file_info)
                    elif status == 'fully_translated':
                        analysis_report['translated_files'].append(file_info)
                elif score >= 0.1:
                    analysis_report['by_score']['low'].append(file_info)
                else:
                    analysis_report['by_score']['none'].append(file_info)
                
                # Fichiers partiellement traduits
                if status == 'partially_translated':
                    analysis_report['partially_translated_files'].append(file_info)
                    
            except Exception as e:
                error_info = {
                    'file': str(file_path),
                    'error': str(e)
                }
                analysis_report['errors'].append(error_info)
        
        # Générer des recommandations
        analysis_report['recommendations'] = self._generate_recommendations_with_translation(analysis_report)
        
        return analysis_report
    
    def _generate_recommendations(self, report: Dict) -> List[str]:
        """Génère des recommandations basées sur l'analyse."""
        recommendations = []
        
        high_score_count = len(report['by_score']['high'])
        medium_score_count = len(report['by_score']['medium'])
        
        if high_score_count > 0:
            recommendations.append(f"🎯 {high_score_count} fichier(s) très prometteur(s) détecté(s)")
            recommendations.append("💡 Commencez par traiter les fichiers avec un score élevé")
        
        if medium_score_count > 0:
            recommendations.append(f"🔍 {medium_score_count} fichier(s) moyennement prometteur(s)")
            recommendations.append("💡 Testez ces fichiers en mode test avant traduction complète")
        
        # Recommandations par format
        for format_name, files in report['by_format'].items():
            if format_name in ['pm1_format', 'pac_format', 'pak_format'] and len(files) > 0:
                recommendations.append(f"🎮 {len(files)} fichier(s) au format {format_name} détecté(s)")
                recommendations.append("💡 Ces formats sont typiques des jeux et méritent une attention particulière")
        
        if len(report['errors']) > 0:
            recommendations.append(f"⚠️ {len(report['errors'])} fichier(s) n'ont pas pu être analysés")
        
        return recommendations
    
    def _generate_recommendations_with_translation(self, report: Dict) -> List[str]:
        """Génère des recommandations basées sur l'analyse incluant le statut de traduction."""
        recommendations = []
        
        # Statistiques de traduction
        total_files = report['analyzed_files']
        translated_count = report['translation_summary']['fully_translated']
        untranslated_count = len(report['untranslated_files'])
        partially_translated_count = report['translation_summary']['partially_translated']
        
        # Calcul du progrès
        if total_files > 0:
            progress_percent = (translated_count / total_files) * 100
            recommendations.append(f"📊 Progrès de traduction: {progress_percent:.1f}% ({translated_count}/{total_files} fichiers)")
        
        # Recommandations basées sur le progrès
        if untranslated_count > 0:
            recommendations.append(f"🎯 {untranslated_count} fichier(s) restant(s) à traduire")
            recommendations.append("💡 Utilisez --auto pour traiter automatiquement les fichiers non traduits")
            
            if untranslated_count <= 5:
                recommendations.append("🏁 Vous êtes proche de la fin ! Quelques fichiers seulement")
            elif untranslated_count <= 20:
                recommendations.append("⚡ Bon progrès ! Environ 20 fichiers ou moins à traiter")
            else:
                recommendations.append("🚀 Beaucoup de fichiers à traiter, le mode automatique est recommandé")
        else:
            recommendations.append("🎉 Tous les fichiers prometteurs semblent déjà traduits !")
        
        if partially_translated_count > 0:
            recommendations.append(f"⚠️ {partially_translated_count} fichier(s) partiellement traduit(s)")
            recommendations.append("💡 Ces fichiers peuvent nécessiter une re-traduction")
        
        if translated_count > 0:
            recommendations.append(f"✅ {translated_count} fichier(s) déjà traduit(s) (ignorés automatiquement)")
        
        # Recommandations par format (inchangées)
        for format_name, files in report['by_format'].items():
            if format_name in ['pm1_format', 'pac_format', 'pak_format'] and len(files) > 0:
                untranslated_in_format = [f for f in files if f.get('translation_status') not in ['fully_translated']]
                if untranslated_in_format:
                    recommendations.append(f"🎮 {len(untranslated_in_format)}/{len(files)} fichier(s) {format_name} à traduire")
        
        if len(report['errors']) > 0:
            recommendations.append(f"⚠️ {len(report['errors'])} fichier(s) n'ont pas pu être analysés")
        
        # Recommandations spécifiques selon la situation
        if untranslated_count == 0 and translated_count > 0:
            recommendations.append("🎊 Traduction complète ! Vous pouvez relancer l'analyse pour vérifier")
        elif untranslated_count > 0 and translated_count > 0:
            recommendations.append("🔄 Reprise de traduction détectée - progression sauvegardée")
        
        return recommendations

class AdaptiveReinsertionManager:
    """Gestionnaire de méthodes de réinsertion adaptatives selon le type de fichier."""
    
    def __init__(self):
        self.reinsertion_strategies = {
            'pm1_format': 'conservative',
            'pac_format': 'aggressive', 
            'pak_format': 'conservative',
            'bf_format': 'safe',
            'tbl_format': 'direct',
            'unknown': 'test_first',
            'text_file': 'direct'
        }
        
        self.test_results = {}
    
    def choose_strategy(self, file_format: str, file_path: Path, test_mode: bool = False) -> str:
        """
        Choisit la stratégie de réinsertion optimale pour un fichier.
        """
        base_strategy = self.reinsertion_strategies.get(file_format, 'test_first')
        
        # Si on a des résultats de test pour ce fichier
        if str(file_path) in self.test_results:
            test_result = self.test_results[str(file_path)]
            if test_result['success']:
                return test_result['best_strategy']
            else:
                return 'safe'  # Fallback sécurisé
        
        # Si mode test activé, toujours tester d'abord
        if test_mode:
            return 'test_first'
            
        return base_strategy
    
    def test_reinsertion_methods(self, file_path: Path, translator) -> Dict:
        """
        Teste différentes méthodes de réinsertion sur un fichier et retourne les résultats.
        """
        test_results = {
            'file': str(file_path),
            'methods_tested': [],
            'success': False,
            'best_strategy': 'safe',
            'details': {}
        }
        
        try:
            # Extraction pour avoir des données de test
            original_texts = translator.extract_texts(file_path)
            if not original_texts:
                test_results['details']['extraction'] = 'failed'
                return test_results
            
            test_results['details']['extraction'] = f'{len(original_texts)} texts extracted'
            
            # Créer des traductions de test (courtes pour minimiser les problèmes)
            test_translations = []
            for text in original_texts:
                if len(text) <= 5:
                    test_translations.append(text)  # Garder les textes très courts
                elif len(text) <= 15:
                    test_translations.append(text[:len(text)-2] + ".")  # Raccourcir légèrement
                else:
                    test_translations.append(text[:len(text)//2] + "...")  # Raccourcir significativement
            
            # Tester différentes stratégies
            strategies_to_test = ['conservative', 'safe', 'aggressive']
            best_score = 0
            best_strategy = 'safe'
            
            for strategy in strategies_to_test:
                strategy_result = self._test_strategy(file_path, test_translations, translator, strategy)
                test_results['methods_tested'].append(strategy)
                test_results['details'][strategy] = strategy_result
                
                if strategy_result['success'] and strategy_result['score'] > best_score:
                    best_score = strategy_result['score']
                    best_strategy = strategy
                    test_results['success'] = True
            
            test_results['best_strategy'] = best_strategy
            
        except Exception as e:
            test_results['details']['error'] = str(e)
            
        return test_results
    
    def _test_strategy(self, file_path: Path, test_translations: List[str], translator, strategy: str) -> Dict:
        """Teste une stratégie spécifique de réinsertion."""
        result = {
            'success': False,
            'score': 0,
            'details': ''
        }
        
        # Créer un fichier de test
        test_file = file_path.with_suffix(f'.test_{strategy}{file_path.suffix}')
        
        try:
            shutil.copy2(file_path, test_file)
            
            # Effectuer l'extraction sur le fichier de test d'abord
            # pour créer le fichier JSON nécessaire
            extracted_texts = translator.extract_texts(test_file)
            if not extracted_texts:
                result['details'] = 'Extraction failed'
                return result
            
            # Sauvegarder la méthode actuelle
            original_method = getattr(translator, '_current_reinsertion_mode', 'default')
            
            # Appliquer la stratégie
            translator._current_reinsertion_mode = strategy
            
            # Tenter la réinsertion
            success = translator.reinsert_texts(test_file, test_translations)
            
            if success:
                # Vérifier l'intégrité en extrayant à nouveau
                new_texts = translator.extract_texts(test_file)
                
                if new_texts and len(new_texts) == len(test_translations):
                    # Calculer un score basé sur les changements détectés
                    changes_detected = sum(1 for old, new in zip(test_translations, new_texts) if old != new)
                    integrity_score = len(new_texts) / len(test_translations)
                    change_score = min(1.0, changes_detected / len(test_translations))
                    
                    result['score'] = (integrity_score * 0.7) + (change_score * 0.3)
                    result['success'] = True
                    result['details'] = f'Changes: {changes_detected}/{len(test_translations)}, Integrity: {integrity_score:.2f}'
                else:
                    result['details'] = 'Integrity check failed'
            else:
                result['details'] = 'Reinsertion failed'
            
            # Restaurer la méthode originale
            translator._current_reinsertion_mode = original_method
            
        except Exception as e:
            result['details'] = f'Exception: {str(e)}'
        finally:
            # Nettoyage
            if test_file.exists():
                test_file.unlink()
        
        return result
    
    def apply_strategy(self, strategy: str, translator, file_path: Path, translations: List[str]) -> bool:
        """Applique une stratégie spécifique de réinsertion."""
        
        if strategy == 'conservative':
            return self._conservative_reinsertion(translator, file_path, translations)
        elif strategy == 'aggressive':
            return self._aggressive_reinsertion(translator, file_path, translations)
        elif strategy == 'safe':
            return self._safe_reinsertion(translator, file_path, translations)
        elif strategy == 'direct':
            return translator.reinsert_texts(file_path, translations)
        else:
            # Fallback vers la méthode standard
            return translator.reinsert_texts(file_path, translations)
    
    def _conservative_reinsertion(self, translator, file_path: Path, translations: List[str]) -> bool:
        """Méthode conservative: utilise maintenant aussi le mode sans limitation."""
        # Nouvelle approche: même en mode conservateur, on accepte les textes longs
        # mais on log plus d'informations pour le suivi
        logging.info(f"Mode conservateur avec réintégration complète pour {file_path.name}")
        return translator.reinsert_texts(file_path, translations)
    
    def _aggressive_reinsertion(self, translator, file_path: Path, translations: List[str]) -> bool:
        """Méthode agressive: réintégration complète avec expansion de fichier si nécessaire."""
        # Mode agressif: accepter TOUS les textes et étendre le fichier si nécessaire
        logging.info(f"Mode agressif avec expansion automatique pour {file_path.name}")
        return translator.reinsert_texts(file_path, translations)
    
    def _safe_reinsertion(self, translator, file_path: Path, translations: List[str]) -> bool:
        """Méthode sûre: crée une sauvegarde et teste avant application finale."""
        # Créer une sauvegarde supplémentaire
        backup_file = file_path.with_suffix(file_path.suffix + f'.safe_backup_{int(time.time())}')
        shutil.copy2(file_path, backup_file)
        
        try:
            # Tenter la réinsertion
            success = translator.reinsert_texts(file_path, translations)
            
            if success:
                # Vérification post-réinsertion
                new_texts = translator.extract_texts(file_path)
                if new_texts and len(new_texts) >= len(translations) * 0.8:  # Au moins 80% des textes
                    logging.info(f"Réinsertion sûre réussie pour {file_path}")
                    return True
                else:
                    # Restaurer depuis la sauvegarde
                    shutil.copy2(backup_file, file_path)
                    logging.warning(f"Réinsertion échouée, fichier restauré pour {file_path}")
                    return False
            else:
                return False
                
        except Exception as e:
            # Restaurer depuis la sauvegarde en cas d'erreur
            if backup_file.exists():
                shutil.copy2(backup_file, file_path)
            logging.error(f"Erreur lors de la réinsertion sûre: {e}")
            return False
        finally:
            # Nettoyage de la sauvegarde temporaire
            if backup_file.exists():
                backup_file.unlink()

class P3FESTranslator:
    def __init__(self, game_dir: str, output_dir: str):
        """
        Initialise le traducteur pour Persona 3 FES.
        
        Args:
            game_dir (str): Chemin vers le répertoire du jeu
            output_dir (str): Chemin vers le répertoire de sortie pour les fichiers traduits
        """
        self.game_dir = Path(game_dir)
        self.output_dir = Path(output_dir)
        self.processed_files = self._load_processed_files()
        self.supported_extensions = {'.pm1', '.pac', '.pak', '.bf', '.tbl'}
        
        # Nouveaux composants pour l'analyse automatique
        self.file_analyzer = FileAnalyzer()
        self.reinsertion_manager = AdaptiveReinsertionManager()
        self.analysis_report = None
        self._current_reinsertion_mode = 'default'
        
        # Création des répertoires nécessaires
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / 'extracted').mkdir(exist_ok=True)
        (self.output_dir / 'translated').mkdir(exist_ok=True)
        (self.output_dir / 'analysis').mkdir(exist_ok=True)
        
        self.special_tokens = SpecialTokens()
        
        # Initialisation du traducteur Google
        self.translator = GoogleTranslator(source='en', target='fr')
        
        # Initialisation du modèle Hugging Face pour l'analyse de texte
        try:
            self.text_classifier = pipeline(
                "text-classification",
                model="facebook/roberta-hate-speech-dynabench-r4-target",
                device=-1  # CPU
            )
            logging.info("Modèle Hugging Face chargé avec succès")
        except Exception as e:
            logging.error(f"Erreur lors du chargement du modèle Hugging Face: {e}")
            self.text_classifier = None

    def _load_processed_files(self) -> Dict[str, str]:
        """Charge la liste des fichiers déjà traités depuis le fichier log."""
        log_file = self.output_dir / 'processed_files.json'
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_processed_files(self):
        """Sauvegarde la liste des fichiers traités dans le fichier log."""
        log_file = self.output_dir / 'processed_files.json'
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(self.processed_files, f, indent=4, ensure_ascii=False)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calcule le hash SHA-256 d'un fichier."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _is_file_modified(self, file_path: Path) -> bool:
        """Vérifie si un fichier a été modifié depuis son dernier traitement."""
        if str(file_path) not in self.processed_files:
            return True
        current_hash = self._calculate_file_hash(file_path)
        return current_hash != self.processed_files[str(file_path)]
    
    def analyze_all_files(self, max_files: int = None) -> Dict:
        """
        Analyse tous les fichiers du répertoire de jeu pour détecter le contenu traduisible.
        """
        logging.info("🔍 Début de l'analyse automatique des fichiers...")
        
        # Utiliser l'analyseur de fichiers
        analysis_report = self.file_analyzer.analyze_directory(self.game_dir, max_files)
        self.analysis_report = analysis_report
        
        # Sauvegarder le rapport d'analyse
        report_file = self.output_dir / 'analysis' / 'file_analysis_report.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_report, f, indent=2, ensure_ascii=False)
        
        logging.info(f"📊 Rapport d'analyse sauvegardé dans {report_file}")
        
        return analysis_report
    
    def print_analysis_summary(self):
        """Affiche un résumé de l'analyse des fichiers incluant le statut de traduction."""
        if not self.analysis_report:
            print("❌ Aucune analyse disponible. Exécutez analyze_all_files() d'abord.")
            return
        
        report = self.analysis_report
        
        print("\n📊 RAPPORT D'ANALYSE INTELLIGENT DES FICHIERS")
        print("=" * 50)
        print(f"📁 Fichiers analysés: {report['analyzed_files']}/{report['total_files']}")
        
        if report.get('ignored_files', 0) > 0:
            print(f"🚫 Fichiers .backup ignorés: {report['ignored_files']}")
        
        # Statistiques de traduction
        summary = report['translation_summary']
        total_with_text = sum(summary.values()) - summary['no_text'] - summary['error']
        
        if total_with_text > 0:
            print(f"\n🔄 STATUT DE TRADUCTION:")
            if summary['fully_translated'] > 0:
                print(f"  ✅ Traduits: {summary['fully_translated']} fichier(s)")
            if summary['partially_translated'] > 0:
                print(f"  🔶 Partiellement traduits: {summary['partially_translated']} fichier(s)")
            if summary['not_translated'] > 0:
                print(f"  ❌ Non traduits: {summary['not_translated']} fichier(s)")
            if summary['unknown'] > 0:
                print(f"  ❓ Statut inconnu: {summary['unknown']} fichier(s)")
            
            # Calcul et affichage du progrès
            translated_count = summary['fully_translated']
            progress_percent = (translated_count / total_with_text) * 100
            progress_bar = "█" * int(progress_percent // 5) + "░" * (20 - int(progress_percent // 5))
            print(f"  📈 Progrès: [{progress_bar}] {progress_percent:.1f}%")
        
        print(f"\n🎯 Fichiers à traiter: {len(report['untranslated_files'])}")
        if len(report['translated_files']) > 0:
            print(f"✅ Fichiers déjà traduits: {len(report['translated_files'])} (ignorés)")
        
        print("\n📋 Répartition par format:")
        for format_name, files in report['by_format'].items():
            if files:
                # Compter les non-traduits par format
                untranslated_in_format = [f for f in files if f.get('translation_status') not in ['fully_translated']]
                translated_in_format = [f for f in files if f.get('translation_status') == 'fully_translated']
                
                status_info = ""
                if translated_in_format and untranslated_in_format:
                    status_info = f" ({len(untranslated_in_format)} à faire, {len(translated_in_format)} faits)"
                elif translated_in_format:
                    status_info = f" (tous traduits)"
                elif untranslated_in_format:
                    status_info = f" (à traduire)"
                
                print(f"  • {format_name}: {len(files)} fichier(s){status_info}")
        
        print("\n📈 Répartition par score de confiance:")
        for score_level, files in report['by_score'].items():
            if files:
                level_names = {
                    'high': 'Élevé (≥70%)',
                    'medium': 'Moyen (40-70%)',
                    'low': 'Faible (10-40%)',
                    'none': 'Très faible (<10%)'
                }
                print(f"  • {level_names.get(score_level, score_level)}: {len(files)} fichier(s)")
        
        if report['errors']:
            print(f"\n⚠️ Erreurs d'analyse: {len(report['errors'])}")
        
        print("\n💡 RECOMMANDATIONS:")
        for recommendation in report['recommendations']:
            print(f"  {recommendation}")
        
        # Affichage des exemples de fichiers partiellement traduits
        if report['partially_translated_files']:
            print(f"\n🔍 FICHIERS PARTIELLEMENT TRADUITS:")
            for file_info in report['partially_translated_files'][:3]:  # Top 3
                examples = file_info.get('translation_examples', [])
                examples_text = ", ".join(examples[:2]) if examples else "Aucun exemple"
                print(f"  📄 {file_info['name']} - Confiance: {file_info['translation_confidence']:.1%}")
                print(f"      Exemples: {examples_text}")
        
        # Affichage des prochains fichiers à traiter
        if len(report['untranslated_files']) > 0:
            print(f"\n📋 PROCHAINS FICHIERS À TRAITER:")
            for file_info in sorted(report['untranslated_files'], key=lambda x: x['text_score'], reverse=True)[:5]:
                score = file_info['text_score']
                format_name = file_info['format']
                print(f"  📄 {file_info['name']} - Score: {score:.1%} ({format_name})")
        
        if len(report['untranslated_files']) == 0 and len(report['translated_files']) > 0:
            print(f"\n🎉 FÉLICITATIONS ! Tous les fichiers prometteurs sont traduits !")
            print(f"   Vous pouvez relancer l'analyse pour vérifier ou affiner les paramètres.")
    
    def get_promising_files(self, min_score: float = 0.3, exclude_translated: bool = True) -> List[Path]:
        """
        Retourne la liste des fichiers prometteurs pour la traduction.
        
        Args:
            min_score: Score minimum pour considérer un fichier comme prometteur
            exclude_translated: Si True, exclut les fichiers déjà traduits
        """
        if not self.analysis_report:
            # Analyser d'abord si pas encore fait
            self.analyze_all_files()
        
        promising_files = []
        
        if exclude_translated:
            # Utiliser la liste des fichiers non traduits
            for file_info in self.analysis_report['untranslated_files']:
                if file_info['text_score'] >= min_score:
                    promising_files.append(Path(file_info['path']))
        else:
            # Utiliser l'ancienne méthode (tous les fichiers prometteurs)
            for file_info in self.analysis_report['promising_files']:
                if file_info['text_score'] >= min_score:
                    promising_files.append(Path(file_info['path']))
        
        return promising_files
    
    def auto_process_directory(self, test_mode: bool = True, min_score: float = 0.4):
        """
        Traite automatiquement tous les fichiers prometteurs du répertoire.
        
        Args:
            test_mode: Si True, teste les méthodes de réinsertion avant application
            min_score: Score minimum pour considérer un fichier comme prometteur
        """
        logging.info("🚀 Début du traitement automatique...")
        
        # Analyser tous les fichiers
        if not self.analysis_report:
            self.analyze_all_files()
        
        # Obtenir les fichiers prometteurs
        promising_files = self.get_promising_files(min_score)
        
        if not promising_files:
            print("❌ Aucun fichier prometteur détecté.")
            return
        
        print(f"📁 {len(promising_files)} fichier(s) sélectionné(s) pour traitement")
        
        # Statistiques
        processed_count = 0
        error_count = 0
        test_results = {}
        
        for i, file_path in enumerate(promising_files, 1):
            print(f"\n📄 [{i}/{len(promising_files)}] Traitement: {file_path.name}")
            
            try:
                # Détecter le format pour choisir la stratégie
                file_format, confidence = self.file_analyzer.detect_file_format(file_path)
                print(f"  🔍 Format détecté: {file_format} (confiance: {confidence:.1%})")
                
                # Si mode test activé, tester les méthodes de réinsertion
                if test_mode:
                    print(f"  🧪 Test des méthodes de réinsertion...")
                    test_result = self.reinsertion_manager.test_reinsertion_methods(file_path, self)
                    test_results[str(file_path)] = test_result
                    
                    if not test_result['success']:
                        print(f"  ⚠️ Aucune méthode de réinsertion fonctionnelle trouvée")
                        error_count += 1
                        continue
                    
                    print(f"  ✅ Meilleure stratégie: {test_result['best_strategy']}")
                
                # Traitement avec la stratégie adaptée
                strategy = self.reinsertion_manager.choose_strategy(file_format, file_path, test_mode)
                print(f"  🔧 Stratégie utilisée: {strategy}")
                
                if self.process_file_with_strategy(file_path, strategy):
                    processed_count += 1
                    print(f"  ✅ Succès")
                else:
                    error_count += 1
                    print(f"  ❌ Échec")
                    
            except Exception as e:
                error_count += 1
                print(f"  ❌ Erreur: {e}")
                logging.error(f"Erreur lors du traitement de {file_path}: {e}")
        
        # Rapport final
        print(f"\n📈 RÉSUMÉ DU TRAITEMENT AUTOMATIQUE")
        print("=" * 40)
        print(f"✅ Fichiers traités avec succès: {processed_count}")
        print(f"❌ Fichiers en erreur: {error_count}")
        print(f"📊 Taux de réussite: {processed_count/(processed_count+error_count)*100:.1f}%")
        
        # Sauvegarder les résultats de test
        if test_results:
            test_report_file = self.output_dir / 'analysis' / 'reinsertion_test_results.json'
            with open(test_report_file, 'w', encoding='utf-8') as f:
                json.dump(test_results, f, indent=2, ensure_ascii=False)
            print(f"📁 Résultats des tests sauvegardés dans {test_report_file}")
    
    def process_file_with_strategy(self, file_path: Path, strategy: str) -> bool:
        """Traite un fichier avec une stratégie spécifique."""
        try:
            # Vérification si déjà traité
            if not self._is_file_modified(file_path):
                logging.info(f"✅ Fichier déjà traité: {file_path.name}")
                return True
            
            logging.info(f"🔄 Début du traitement avec stratégie '{strategy}': {file_path.name}")
            
            # Extraction
            texts = self.extract_texts(file_path)
            if not texts:
                logging.warning(f"Aucun texte extrait de {file_path}")
                return True  # Pas d'erreur, juste rien à traduire
            
            # Traduction
            translated_texts = self.translate_texts(texts, file_path)
            
            # Réinsertion avec stratégie adaptée
            if strategy == 'default':
                success = self.reinsert_texts(file_path, translated_texts)
            else:
                success = self.reinsertion_manager.apply_strategy(strategy, self, file_path, translated_texts)
            
            if success:
                # Marquer comme traité
                self.processed_files[str(file_path)] = self._calculate_file_hash(file_path)
                self._save_processed_files()
                logging.info(f"✅ Traitement terminé avec succès: {file_path.name}")
                return True
            else:
                logging.error(f"❌ Échec de la réinsertion: {file_path.name}")
                return False
                
        except Exception as e:
            logging.error(f"❌ Erreur lors du traitement de {file_path}: {e}")
            return False
    
    def extract_texts(self, file_path: Path) -> Optional[List[str]]:
        """
        Extraction simple et robuste des textes pour tous les formats supportés.
        """
        # Nouveau système: pas de vérification d'extension, on teste tous les fichiers
        out_json = self.output_dir / 'extracted' / (file_path.stem + '.json')

        try:
            with open(file_path, 'rb') as f:
                data = f.read()

            messages = []
            texts = []
            
            # Patterns multiples pour une meilleure extraction
            patterns = [
                rb'[\x20-\x7E\x80-\xFF]{8,}',  # Chaînes ASCII étendues
                rb'[\x20-\x7E]{4,}',           # Chaînes ASCII standard
            ]
            
            all_matches = set()
            for pattern in patterns:
                matches = re.finditer(pattern, data)
                for match in matches:
                    if match.group() not in all_matches:
                        all_matches.add(match.group())
                        
                        # Essayer plusieurs encodages
                        text = None
                        for encoding in ['ascii', 'shift_jis', 'utf-8', 'latin1']:
                            try:
                                text = match.group().decode(encoding).strip()
                                if len(text) >= 4 and self._is_likely_game_text(text):
                                    break
                                text = None
                            except:
                                continue
                        
                        if text:
                            offset = match.start()
                            messages.append({
                                'offset': offset,
                                'raw': match.group().hex(),
                                'encoding': encoding,
                                'texts': [text]
                            })
                            texts.append(text)

            # Sauvegarde des messages extraits
            with open(out_json, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            
            logging.info(f"{len(texts)} textes extraits de {file_path}")
            return texts

        except Exception as e:
            logging.error(f"Erreur extraction: {e}")
            return None
    
    def _is_likely_game_text(self, text: str) -> bool:
        """Détermine si le texte ressemble à du texte de jeu traduisible."""
        # Filtres de base
        if len(text.strip()) < 4:
            return False
            
        # Ignore les chaînes qui ne contiennent que des caractères spéciaux
        if not any(c.isalpha() for c in text):
            return False
            
        # Ignore les chaînes avec trop de caractères répétés
        if len(set(text)) < len(text) / 3:
            return False
            
        # Ignore les chemins de fichiers évidents
        if '/' in text or '\\' in text or text.endswith('.exe'):
            return False
            
        return True

    def translate_texts(self, texts: List[str], file_path: Path = None) -> List[str]:
        """
        Traduit les textes de l'anglais vers le français avec Google Translator.
        """
        import time
        import json
        import re
        import sys

        # Liste blanche personnalisable de noms propres à ne jamais traduire
        whitelist = [
            "Yukari", "Mitsuru", "Fuuka", "Akihiko", "Tartarus", "Nyx", "SEES", "Aigis", "Junpei", "Shinjiro", "Koromaru", "Elizabeth", "Igor", "Pharos", "Ryoji", "Chidori", "Strega", "Ikutsuki", "Takaya", "Jin", "Ken", "Persona", "Evoker", "S.E.E.S.", "Aragaki", "Makoto", "Minato", "Protagonist", "Yamagishi", "Sanada", "Takeba", "Iori", "Amada", "Tanaka", "Velvet Room", "Paulownia Mall", "Gekkoukan", "Mitsuru Kirijo", "Yukari Takeba", "Fuuka Yamagishi", "Akihiko Sanada", "Junpei Iori", "Shinjiro Aragaki", "Ken Amada", "Koromaru", "Aigis", "Elizabeth", "Igor", "Pharos", "Ryoji Mochizuki", "Chidori", "Takaya", "Jin", "Ikutsuki", "Strega", "Nyx Avatar", "Nyx", "Tartarus", "SEES", "Persona", "Evoker", "S.E.E.S."
        ]

        translated = []
        
        try:
            total_texts = len(texts)
            
            for i, text in enumerate(texts, 1):
                self.print_progress(i, total_texts, text)
                
                # Extraction des tokens et du texte propre
                tokens, clean_text = self.special_tokens.extract_game_tokens(text)
                
                # Récupération du contexte
                previous_text = texts[i-2] if i > 1 else None
                next_text = texts[i] if i < len(texts) else None
                
                if not clean_text.strip() or self.should_skip_translation(text, whitelist, previous_text, next_text):
                    translated.append(text)
                    continue
                    
                try:
                    # Traduction avec Google Translate
                    fr = self.translator.translate(clean_text)
                    if not fr:  # Si la traduction échoue
                        logging.warning(f"Échec de la traduction pour '{text}', retour au texte original")
                        fr = text
                except Exception as e:
                    logging.error(f"Erreur lors de la traduction de '{text}': {e}")
                    fr = text
                
                # Reconstruction avec les tokens originaux
                fr = self.special_tokens.reconstruct_text(fr, tokens)
                translated.append(fr)
                time.sleep(0.5)  # Pause pour respecter les limites d'API
            
            print()

        except Exception as e:
            logging.error(f"Erreur lors de la traduction : {e}")
            return texts

        # Sauvegarde dans un fichier à part si file_path est fourni
        if file_path is not None:
            out_json = self.output_dir / 'translated' / (file_path.stem + '_fr.json')
            try:
                with open(out_json, 'w', encoding='utf-8') as f:
                    json.dump(translated, f, ensure_ascii=False, indent=2)
                logging.info(f"Textes traduits sauvegardés dans {out_json}")
            except Exception as e:
                logging.error(f"Erreur lors de la sauvegarde des textes traduits : {e}")
        
        return translated
    
    def reinsert_texts(self, file_path, translated_texts: List[str]) -> bool:
        """
        Réinsère les textes traduits dans le fichier original de manière sécurisée.
        Version simplifiée et robuste.
        """
        import json
        import shutil
        
        # S'assurer que file_path est un Path object
        if isinstance(file_path, str):
            file_path = Path(file_path)
        elif not isinstance(file_path, Path):
            file_path = Path(str(file_path))
        
        # Création du dossier de sortie
        output_dir = self.output_dir / 'reinjected'
        output_dir.mkdir(exist_ok=True)
        out_file = output_dir / file_path.name
        
        try:
            # Chargement du fichier d'extraction
            extracted_json = self.output_dir / 'extracted' / (file_path.stem + '.json')
            if not extracted_json.exists():
                logging.error(f"Fichier d'extraction manquant : {extracted_json}")
                return False
                
            with open(extracted_json, 'r', encoding='utf-8') as f:
                messages = json.load(f)
                
            if len(messages) != len(translated_texts):
                logging.error(f"Nombre de textes traduits ({len(translated_texts)}) != messages extraits ({len(messages)})")
                return False
            
            # Lecture du fichier original
            with open(file_path, 'rb') as f:
                data = bytearray(f.read())
            
            # Préparation des remplacements (en ordre inverse pour ne pas décaler les offsets)
            replacements = []
            for msg, new_text in zip(messages, translated_texts):
                if 'offset' in msg and 'texts' in msg and msg['texts']:
                    old_text = msg['texts'][0]
                    
                    # Essai de différents encodages pour le texte original
                    old_bytes = None
                    used_encoding = 'utf-8'  # Commencer par UTF-8 pour supporter les caractères français
                    for encoding in ['utf-8', 'ascii', 'shift_jis', 'latin1']:
                        try:
                            test_bytes = old_text.encode(encoding)
                            if data.find(test_bytes) != -1:
                                old_bytes = test_bytes
                                used_encoding = encoding
                                break
                        except:
                            continue
                    
                    if old_bytes is None:
                        logging.warning(f"Impossible de trouver '{old_text}' dans le fichier")
                        continue
                    
                    # Encodage du nouveau texte avec le même encodage
                    try:
                        new_bytes = new_text.encode(used_encoding)
                    except UnicodeEncodeError:
                        # Si l'encodage original ne supporte pas le français, essayer UTF-8
                        try:
                            new_bytes = new_text.encode('utf-8')
                            used_encoding = 'utf-8'
                            logging.info(f"Passage en UTF-8 pour '{new_text}' (caractères français détectés)")
                        except:
                            logging.warning(f"Impossible d'encoder '{new_text}', utilisation de l'original")
                            new_bytes = old_bytes
                    
                    # STRATÉGIE SANS LIMITATION: Réintégrer TOUS les textes peu importe la taille
                    if len(new_bytes) > len(old_bytes):
                        # Aucune limitation ! Traduction complète avec expansion automatique
                        overflow = len(new_bytes) - len(old_bytes)
                        expansion_percent = (overflow / len(old_bytes)) * 100
                        logging.info(f"🚀 Expansion automatique: '{old_text}' -> '{new_text}' (+{overflow} bytes, +{expansion_percent:.1f}%)")
                        # new_bytes reste inchangé - expansion complète garantie !
                        
                    elif len(new_bytes) < len(old_bytes):
                        # Padding avec des espaces ou des zéros
                        if used_encoding in ['ascii', 'utf-8', 'latin1']:
                            padding_char = b' '
                        else:
                            padding_char = b'\x00'
                        new_bytes = new_bytes + padding_char * (len(old_bytes) - len(new_bytes))
                    
                    # Recherche de la position du texte original
                    offset = data.find(old_bytes)
                    if offset != -1:
                        replacements.append({
                            'offset': offset,
                            'old_bytes': old_bytes,
                            'new_bytes': new_bytes
                        })
                    else:
                        logging.warning(f"Texte original non trouvé dans le fichier: '{old_text}'")
            
            # Application des remplacements avec gestion dynamique de la taille
            replacements.sort(key=lambda x: x['offset'], reverse=True)
            successful_replacements = 0
            total_size_change = 0
            
            for replacement in replacements:
                offset = replacement['offset']
                old_bytes = replacement['old_bytes']
                new_bytes = replacement['new_bytes']
                
                # Ajuster l'offset si des remplacements précédents ont changé la taille
                adjusted_offset = offset + total_size_change
                
                # Vérification de sécurité avec offset ajusté
                if adjusted_offset >= 0 and adjusted_offset + len(old_bytes) <= len(data):
                    if data[adjusted_offset:adjusted_offset+len(old_bytes)] == old_bytes:
                        # Calculer le changement de taille
                        size_diff = len(new_bytes) - len(old_bytes)
                        
                        # Remplacer avec la nouvelle taille (peut être plus grande !)
                        data[adjusted_offset:adjusted_offset+len(old_bytes)] = new_bytes
                        
                        # Mettre à jour le changement total de taille
                        total_size_change += size_diff
                        successful_replacements += 1
                        
                        if size_diff > 0:
                            logging.info(f"✅ Remplacement étendu réussi à l'offset {adjusted_offset} (+{size_diff} bytes)")
                        else:
                            logging.debug(f"Remplacement réussi à l'offset {adjusted_offset}")
                    else:
                        logging.warning(f"Données à l'offset {adjusted_offset} ne correspondent pas, remplacement ignoré")
                else:
                    logging.warning(f"Offset {adjusted_offset} hors limites, remplacement ignoré")
            
            logging.info(f"📊 {successful_replacements}/{len(replacements)} remplacements réussis, taille finale: {len(data)} bytes")
            
            # Sauvegarde du fichier modifié
            with open(out_file, 'wb') as f:
                f.write(data)
            logging.info(f"Fichier réinjecté sauvegardé : {out_file}")
            
            # Copie de sécurité de l'original (si ce n'est pas déjà fait)
            backup_file = file_path.with_suffix(file_path.suffix + '.backup')
            if not backup_file.exists():
                shutil.copy2(file_path, backup_file)
                logging.info(f"Sauvegarde créée : {backup_file}")
            
            # Remplacement du fichier original
            try:
                shutil.copy2(out_file, file_path)
                logging.info(f"Fichier original mis à jour : {file_path}")
                return True
            except Exception as e:
                logging.error(f"Erreur lors de la mise à jour du fichier original : {e}")
                logging.info(f"Le fichier traduit est disponible dans : {out_file}")
                return False
                
        except Exception as e:
            logging.error(f"Erreur lors de la réinsertion : {e}")
            return False
    
    def validate_integration_quality(self, file_path: Path) -> Dict:
        """
        Valide la qualité de l'intégration après réinsertion.
        Retourne un rapport détaillé.
        """
        try:
            # Extraire les textes du fichier modifié
            new_texts = self.extract_texts(file_path)
            
            # Analyser le statut de traduction
            translation_status = self.file_analyzer.detect_translation_status(file_path)
            
            # Statistiques
            validation_report = {
                'file': str(file_path),
                'texts_found': len(new_texts) if new_texts else 0,
                'translation_status': translation_status['status'],
                'french_ratio': translation_status['confidence'],
                'quality_score': 0.0,
                'recommendations': []
            }
            
            # Calculer le score de qualité
            if new_texts and len(new_texts) > 0:
                # Compter les textes français vs anglais
                french_count = translation_status.get('french_indicators', 0)
                english_count = translation_status.get('english_indicators', 0)
                total_indicators = french_count + english_count
                
                if total_indicators > 0:
                    french_ratio = french_count / total_indicators
                    validation_report['quality_score'] = french_ratio
                    
                    if french_ratio >= 0.8:
                        validation_report['recommendations'].append("✅ Excellente qualité de traduction")
                    elif french_ratio >= 0.5:
                        validation_report['recommendations'].append("✅ Bonne qualité de traduction")  
                    elif french_ratio >= 0.2:
                        validation_report['recommendations'].append("⚠️ Traduction partielle détectée")
                    else:
                        validation_report['recommendations'].append("❌ Peu de traductions détectées")
                else:
                    validation_report['recommendations'].append("ℹ️ Aucun indicateur de langue détecté")
            else:
                validation_report['recommendations'].append("⚠️ Aucun texte extrait du fichier")
            
            # Vérifier la taille du fichier
            file_size = file_path.stat().st_size
            validation_report['file_size'] = file_size
            
            if file_size > 1024 * 1024:  # > 1MB
                validation_report['recommendations'].append(f"📊 Fichier volumineux: {file_size // 1024}KB (expansion réussie)")
            
            return validation_report
            
        except Exception as e:
            return {
                'file': str(file_path),
                'error': str(e),
                'quality_score': 0.0,
                'recommendations': [f"❌ Erreur de validation: {e}"]
            }
    
    def process_file(self, file_path: Path) -> bool:
        """Traite un fichier complet (extraction, traduction, réinsertion)."""
        # Vérification si le fichier a déjà été traité
        if not self._is_file_modified(file_path):
            logging.info(f"✅ Fichier déjà traité et non modifié: {file_path.name}")
            return True
            
        logging.info(f"🔄 Début du traitement: {file_path.name}")
        
        try:
            # Étape 1: Extraction
            logging.info(f"  📤 Extraction des textes...")
            texts = self.extract_texts(file_path)
            if texts is None:
                logging.error(f"  ❌ Échec de l'extraction")
                return False
                
            # Vérification si le fichier contient des textes à traduire
            if not texts:
                logging.info(f"  ℹ️ Aucun texte à traduire trouvé, fichier marqué comme traité")
                # Enregistrer le fichier comme traité même s'il n'y a pas de textes
                self.processed_files[str(file_path)] = self._calculate_file_hash(file_path)
                self._save_processed_files()
                return True
            
            logging.info(f"  📝 {len(texts)} texte(s) extrait(s)")
            
            # Étape 2: Traduction
            logging.info(f"  🔄 Traduction en cours...")
            translated_texts = self.translate_texts(texts, file_path)
            
            # Étape 3: Réinsertion
            logging.info(f"  📥 Réinsertion des textes traduits...")
            if not self.reinsert_texts(file_path, translated_texts):
                logging.error(f"  ❌ Échec de la réinsertion")
                return False
            
            # Étape 4: Validation de la qualité
            logging.info(f"  🔍 Validation de la qualité d'intégration...")
            validation = self.validate_integration_quality(file_path)
            
            quality_score = validation['quality_score']
            logging.info(f"  📊 Score de qualité: {quality_score:.1%}")
            
            for recommendation in validation['recommendations']:
                logging.info(f"  {recommendation}")
            
            if quality_score >= 0.5:
                logging.info(f"  ✅ Qualité d'intégration validée")
            else:
                logging.warning(f"  ⚠️ Qualité d'intégration à vérifier manuellement")
            
            logging.info(f"  ✅ Traitement terminé avec succès")
            
            # Mise à jour du hash du fichier
            self.processed_files[str(file_path)] = self._calculate_file_hash(file_path)
            self._save_processed_files()
            return True
            
        except Exception as e:
            logging.error(f"  ❌ Erreur lors du traitement de {file_path.name}: {str(e)}")
            return False
    
    def process_directory(self):
        """Traite tous les fichiers du répertoire du jeu avec l'ancienne méthode."""
        print("🔄 Mode de traitement traditionnel activé...")
        print("💡 Utilisez --auto pour le nouveau mode d'analyse automatique")
        
        processed_count = 0
        error_count = 0
        ignored_count = 0
        
        # Recherche de tous les fichiers supportés (ancienne méthode)
        all_files = []
        for root, _, files in os.walk(self.game_dir):
            for file in files:
                file_path = Path(root) / file
                # Ignorer les fichiers .backup
                if file_path.suffix.lower() == '.backup' or '.backup' in file_path.name:
                    ignored_count += 1
                    continue
                if file_path.suffix.lower() in self.supported_extensions:
                    all_files.append(file_path)
        
        if not all_files:
            print(f"❌ Aucun fichier supporté trouvé dans {self.game_dir}")
            print(f"📁 Extensions supportées: {', '.join(self.supported_extensions)}")
            if ignored_count > 0:
                print(f"🚫 {ignored_count} fichier(s) .backup ignoré(s)")
            return
            
        print(f"📊 {len(all_files)} fichier(s) trouvé(s) à traiter")
        if ignored_count > 0:
            print(f"🚫 {ignored_count} fichier(s) .backup ignoré(s)")
        
        for i, file_path in enumerate(all_files, 1):
            print(f"\n📄 [{i}/{len(all_files)}] Traitement: {file_path.name}")
            try:
                if self.process_file(file_path):
                    processed_count += 1
                    print(f"✅ Succès")
                else:
                    error_count += 1
                    print(f"❌ Échec")
            except Exception as e:
                error_count += 1
                print(f"❌ Erreur: {e}")
                
        print(f"\n📈 Résumé: {processed_count} réussis, {error_count} échecs")
    
    def test_mode(self):
        """Mode test pour analyser les fichiers sans traduction."""
        print("🧪 Mode test activé - Analyse des fichiers...")
        
        for root, _, files in os.walk(self.game_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.supported_extensions:
                    print(f"\n📄 Analyse: {file_path}")
                    
                    try:
                        texts = self.extract_texts(file_path)
                        if texts:
                            print(f"  📝 {len(texts)} texte(s) extrait(s)")
                            # Afficher les premiers textes
                            for i, text in enumerate(texts[:5]):
                                print(f"    {i+1}. {text[:60]}...")
                            if len(texts) > 5:
                                print(f"    ... et {len(texts)-5} autre(s)")
                        else:
                            print(f"  ❌ Aucun texte extrait")
                    except Exception as e:
                        print(f"  ❌ Erreur: {e}")

    def print_progress(self, current: int, total: int, text: str):
        """Affiche la progression de la traduction avec le texte en cours."""
        progress = (current / total) * 100
        sys.stdout.write(f"\rTraduction en cours : {progress:.1f}% - Texte {current}/{total}: {text[:50]}...")
        sys.stdout.flush()

    def should_skip_translation(self, text: str, whitelist: List[str], previous_text: str = None, next_text: str = None) -> bool:
        """Version simplifiée qui traduit plus de textes."""
        clean_text = text.strip()
        
        # Si le texte est vide
        if not clean_text:
            return True
            
        # Si le texte est dans la whitelist des noms propres
        if any(name.lower() in clean_text.lower() for name in whitelist):
            return False  # On traduit quand même pour le contexte
            
        # Patterns vraiment critiques à ignorer
        skip_patterns = [
            r'^\d+$',                    # Nombres seuls
            r'^[A-Z0-9_]{6,}$',         # Codes longs en majuscules
            r'^[\x00-\x1F]+$',          # Caractères de contrôle
            r'^[!@#$%^&*()_+\-=\[\]{};\'"\\|,.<>\/?]+$',  # Que des symboles
        ]
        
        for pattern in skip_patterns:
            if re.match(pattern, clean_text):
                return True
        
        # Si c'est trop court et sans voyelles
        if len(clean_text) < 3 and not any(v in clean_text.lower() for v in 'aeiouy'):
            return True
            
        return False

def main():
    """Point d'entrée principal du programme."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Traducteur automatique pour Persona 3 FES')
    parser.add_argument('--game-dir', default='GameFiles', help='Dossier contenant les fichiers du jeu')
    parser.add_argument('--output-dir', default='TranslatedFiles', help='Dossier de sortie')
    parser.add_argument('--file', help='Traduire un fichier spécifique')
    parser.add_argument('--test', action='store_true', help='Mode test (analyse sans traduction)')
    parser.add_argument('--verbose', action='store_true', help='Mode verbose')
    
    # Nouvelles options pour l'analyse automatique
    parser.add_argument('--analyze', action='store_true', help='Analyser tous les fichiers pour détecter le contenu traduisible')
    parser.add_argument('--auto', action='store_true', help='Mode automatique: analyse + traitement intelligent')
    parser.add_argument('--auto-test', action='store_true', help='Mode automatique avec test des méthodes de réinsertion')
    parser.add_argument('--min-score', type=float, default=0.4, help='Score minimum pour considérer un fichier (0.0-1.0)')
    parser.add_argument('--max-files', type=int, help='Limite le nombre de fichiers à analyser')
    parser.add_argument('--remaining', action='store_true', help='Affiche seulement les fichiers restants à traduire')
    parser.add_argument('--progress', action='store_true', help='Affiche le progrès de traduction et statistiques détaillées')
    parser.add_argument('--validate', action='store_true', help='Valide la qualité des traductions dans les fichiers existants')
    parser.add_argument('--validate-file', help='Valide la qualité de traduction d\'un fichier spécifique')
    
    # Nouvelle option pour la stratégie de traduction
    parser.add_argument('--strategy', choices=['professional', 'preserve', 'mixed'], 
                       default='professional', 
                       help='Stratégie pour gérer les traductions trop longues (défaut: professional)')
    parser.add_argument('--show-strategies', action='store_true', 
                       help='Affiche les stratégies disponibles et leurs descriptions')
    
    args = parser.parse_args()
    
    # Afficher les stratégies disponibles si demandé
    if args.show_strategies:
        print("🎯 Stratégies de Traduction:")
        print("=" * 40)
        print("📋 AGGRESSIVE - Aucune limitation de taille")
        print("   Réintègre TOUS les textes peu importe leur longueur")
        print("   • Préserve la qualité: ✅")
        print("   • Traductions complètes: ✅") 
        print("   • Aucune troncature: ✅")
        print(f"\n💡 Mode actuel: Réintégration sans limitation")
        return
    
    print(f"🎮 Stratégie de traduction: {args.strategy.upper()}")
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Vérification que le dossier de jeu existe
    if not Path(args.game_dir).exists():
        print(f"❌ Erreur: Le dossier '{args.game_dir}' n'existe pas.")
        print(f"📁 Créez le dossier et placez-y vos fichiers .pm1, .pac, .pak, .bf, .tbl")
        sys.exit(1)
    
    try:
        translator = P3FESTranslator(args.game_dir, args.output_dir)
        
        if args.file:
            # Traitement d'un fichier spécifique
            file_path = Path(args.file)
            if file_path.exists():
                print(f"🔄 Traitement du fichier: {file_path}")
                success = translator.process_file(file_path)
                print(f"✅ Succès" if success else f"❌ Échec")
            else:
                print(f"❌ Fichier non trouvé: {file_path}")
                
        elif args.analyze:
            # Mode analyse seulement
            print("🔍 Mode analyse - Détection des fichiers traduisibles...")
            analysis_report = translator.analyze_all_files(args.max_files)
            translator.print_analysis_summary()
            
        elif args.remaining:
            # Mode affichage des fichiers restants
            print("📋 Analyse des fichiers restants à traduire...")
            analysis_report = translator.analyze_all_files(args.max_files)
            
            remaining_files = translator.get_promising_files(args.min_score, exclude_translated=True)
            translated_files = len(analysis_report.get('translated_files', []))
            
            print(f"\n📊 FICHIERS RESTANTS À TRADUIRE")
            print("=" * 35)
            print(f"✅ Fichiers déjà traduits: {translated_files}")
            print(f"🎯 Fichiers restants: {len(remaining_files)}")
            
            if remaining_files:
                print(f"\n📋 LISTE DES FICHIERS À TRADUIRE:")
                for i, file_path in enumerate(remaining_files, 1):
                    # Obtenir les infos détaillées
                    file_info = None
                    for info in analysis_report['untranslated_files']:
                        if Path(info['path']) == file_path:
                            file_info = info
                            break
                    
                    if file_info:
                        score = file_info['text_score']
                        format_name = file_info['format']
                        size_kb = file_info['size'] // 1024
                        print(f"  {i:2d}. {file_path.name}")
                        print(f"      Score: {score:.1%} | Format: {format_name} | Taille: {size_kb}KB")
                    else:
                        print(f"  {i:2d}. {file_path.name}")
                
                estimated_time = len(remaining_files) * 2  # 2 minutes par fichier en moyenne
                print(f"\n⏱️ Temps estimé: ~{estimated_time} minutes")
                print(f"💡 Commande recommandée: python p3fes_translator.py --auto-test")
            else:
                print(f"\n🎉 FÉLICITATIONS ! Tous les fichiers semblent déjà traduits !")
                
        elif args.progress:
            # Mode affichage du progrès détaillé
            print("📈 Analyse du progrès de traduction...")
            analysis_report = translator.analyze_all_files(args.max_files)
            
            summary = analysis_report['translation_summary']
            total_files = analysis_report['analyzed_files']
            translated = summary['fully_translated']
            partial = summary['partially_translated']
            untranslated = summary['not_translated']
            
            print(f"\n📊 PROGRÈS DE TRADUCTION DÉTAILLÉ")
            print("=" * 40)
            print(f"📁 Total des fichiers: {total_files}")
            print(f"✅ Traduits: {translated} ({translated/total_files*100:.1f}%)")
            print(f"🔶 Partiellement: {partial} ({partial/total_files*100:.1f}%)")
            print(f"❌ Non traduits: {untranslated} ({untranslated/total_files*100:.1f}%)")
            
            # Barre de progrès ASCII
            progress_percent = (translated / total_files) * 100 if total_files > 0 else 0
            bar_length = 30
            filled_length = int(bar_length * translated // total_files) if total_files > 0 else 0
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            print(f"\n📈 [{bar}] {progress_percent:.1f}%")
            
            # Statistiques par format
            print(f"\n📋 PROGRÈS PAR FORMAT:")
            for format_name, files in analysis_report['by_format'].items():
                if files:
                    format_translated = len([f for f in files if f.get('translation_status') == 'fully_translated'])
                    format_total = len(files)
                    format_percent = (format_translated / format_total * 100) if format_total > 0 else 0
                    print(f"  • {format_name}: {format_translated}/{format_total} ({format_percent:.1f}%)")
            
            remaining_count = len(analysis_report.get('untranslated_files', []))
            if remaining_count > 0:
                print(f"\n🎯 {remaining_count} fichier(s) restant(s) à traiter")
                print(f"💡 Utilisez --remaining pour voir la liste détaillée")
            
        elif args.validate:
            # Mode validation de qualité
            print("🔍 Validation de la qualité des traductions existantes...")
            analysis_report = translator.analyze_all_files(args.max_files)
            
            # Valider seulement les fichiers traduits
            translated_files = analysis_report.get('translated_files', [])
            
            if not translated_files:
                print("❌ Aucun fichier traduit détecté pour validation")
            else:
                print(f"📊 Validation de {len(translated_files)} fichier(s) traduit(s)...")
                
                total_quality = 0.0
                validated_count = 0
                
                for file_info in translated_files:
                    file_path = Path(file_info['path'])
                    print(f"\n📄 Validation: {file_path.name}")
                    
                    validation = translator.validate_integration_quality(file_path)
                    quality = validation['quality_score']
                    
                    print(f"  📊 Score de qualité: {quality:.1%}")
                    for rec in validation['recommendations']:
                        print(f"  {rec}")
                    
                    total_quality += quality
                    validated_count += 1
                
                if validated_count > 0:
                    avg_quality = total_quality / validated_count
                    print(f"\n📈 RÉSUMÉ DE VALIDATION:")
                    print(f"  📊 Qualité moyenne: {avg_quality:.1%}")
                    print(f"  📁 Fichiers validés: {validated_count}")
                    
                    if avg_quality >= 0.8:
                        print(f"  🎉 Excellente qualité globale !")
                    elif avg_quality >= 0.6:
                        print(f"  ✅ Bonne qualité globale")
                    else:
                        print(f"  ⚠️ Qualité à améliorer")
                        
        elif args.validate_file:
            # Validation d'un fichier spécifique
            file_path = Path(args.validate_file)
            if file_path.exists():
                print(f"🔍 Validation de la qualité: {file_path}")
                validation = translator.validate_integration_quality(file_path)
                
                print(f"📊 Score de qualité: {validation['quality_score']:.1%}")
                print(f"📝 Textes trouvés: {validation['texts_found']}")
                print(f"🔄 Statut: {validation['translation_status']}")
                
                print(f"\n💡 Recommandations:")
                for rec in validation['recommendations']:
                    print(f"  {rec}")
            else:
                print(f"❌ Fichier non trouvé: {file_path}")
            
        elif args.auto or args.auto_test:
            # Mode automatique
            test_mode = args.auto_test
            print(f"🤖 Mode automatique {'avec tests' if test_mode else 'standard'}")
            translator.auto_process_directory(test_mode=test_mode, min_score=args.min_score)
            
        elif args.test:
            # Mode test traditionnel
            print("🧪 Mode test - Analyse des fichiers sans traduction...")
            translator.test_mode()
            
        else:
            # Mode traditionnel
            print("🚀 Mode traditionnel - Traitement des fichiers par extension...")
            translator.process_directory()
            
    except KeyboardInterrupt:
        print("\n⏹️ Arrêt demandé par l'utilisateur")
    except Exception as e:
        logging.error(f"Erreur fatale: {e}")
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()