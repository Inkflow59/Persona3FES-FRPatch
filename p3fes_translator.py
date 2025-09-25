#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import shutil
from datetime import datetime, timedelta
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
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

# Interface graphique optionnelle
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    logging.warning("Interface graphique non disponible (tkinter manquant)")

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

class TranslationCache:
    """Cache SQLite intelligent pour les traductions avec TTL."""
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24*7):
        self.cache_file = cache_dir / "translation_cache.db"
        self.ttl = timedelta(hours=ttl_hours)
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._lock = threading.Lock()
    
    def _init_db(self):
        """Initialise la base de données SQLite."""
        with sqlite3.connect(self.cache_file) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS translations (
                    text_hash TEXT PRIMARY KEY,
                    original_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON translations(created_at)')
    
    def get(self, text: str) -> Optional[str]:
        """Récupère une traduction du cache."""
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        
        with self._lock:
            with sqlite3.connect(self.cache_file) as conn:
                cursor = conn.execute(
                    'SELECT translated_text, created_at FROM translations WHERE text_hash = ?',
                    (text_hash,)
                )
                row = cursor.fetchone()
                
                if row:
                    created_at = datetime.fromisoformat(row[1])
                    if datetime.now() - created_at < self.ttl:
                        # Mettre à jour les stats d'accès
                        conn.execute(
                            'UPDATE translations SET accessed_at = ?, access_count = access_count + 1 WHERE text_hash = ?',
                            (datetime.now().isoformat(), text_hash)
                        )
                        return row[0]
                    else:
                        # Supprimer l'entrée expirée
                        conn.execute('DELETE FROM translations WHERE text_hash = ?', (text_hash,))
        return None
    
    def put(self, text: str, translation: str):
        """Stocke une traduction dans le cache."""
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        now = datetime.now().isoformat()
        
        with self._lock:
            with sqlite3.connect(self.cache_file) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO translations 
                    (text_hash, original_text, translated_text, created_at, accessed_at, access_count)
                    VALUES (?, ?, ?, ?, ?, 1)
                ''', (text_hash, text, translation, now, now))
    
    def cleanup_expired(self) -> int:
        """Nettoie les entrées expirées."""
        cutoff = datetime.now() - self.ttl
        with self._lock:
            with sqlite3.connect(self.cache_file) as conn:
                cursor = conn.execute(
                    'DELETE FROM translations WHERE datetime(created_at) < ?',
                    (cutoff.isoformat(),)
                )
                return cursor.rowcount
    
    def get_stats(self) -> Dict:
        """Retourne les statistiques du cache."""
        with self._lock:
            with sqlite3.connect(self.cache_file) as conn:
                cursor = conn.execute('''
                    SELECT COUNT(*) as total,
                           SUM(access_count) as total_hits,
                           COUNT(CASE WHEN datetime(created_at) > datetime('now', '-24 hours') THEN 1 END) as recent
                    FROM translations
                ''')
                row = cursor.fetchone()
                return {
                    'total_entries': row[0] or 0,
                    'total_hits': row[1] or 0,
                    'recent_entries': row[2] or 0
                }

class EnhancedTranslationService:
    """Service de traduction amélioré avec retry, cache et fallback."""
    
    def __init__(self, cache_dir: Path):
        self.cache = TranslationCache(cache_dir)
        self.translator = GoogleTranslator(source='en', target='fr')
        self.stats = {
            'translations_requested': 0,
            'cache_hits': 0,
            'translation_errors': 0,
            'successful_translations': 0
        }
        self._session = requests.Session()
        # Configuration retry pour requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
    
    def translate_with_retry(self, text: str, max_retries: int = 3) -> str:
        """Traduit un texte avec retry automatique."""
        self.stats['translations_requested'] += 1
        
        # Vérifier le cache d'abord
        cached = self.cache.get(text)
        if cached:
            self.stats['cache_hits'] += 1
            return cached
        
        # Essayer la traduction avec retry
        for attempt in range(max_retries):
            try:
                translated = self.translator.translate(text)
                if translated and translated.strip():
                    # Succès - sauvegarder dans le cache
                    self.cache.put(text, translated)
                    self.stats['successful_translations'] += 1
                    return translated
            except Exception as e:
                logging.warning(f"Tentative {attempt + 1}/{max_retries} échouée: {e}")
                if attempt < max_retries - 1:
                    time.sleep(min(2 ** attempt, 10))  # Backoff exponentiel
        
        # Toutes les tentatives ont échoué
        self.stats['translation_errors'] += 1
        logging.error(f"Échec complet de traduction pour '{text[:50]}...'")
        return text  # Retourner le texte original
    
    def translate_batch(self, texts: List[str], max_workers: int = 3) -> List[str]:
        """Traduit un lot de textes en parallèle."""
        if not texts:
            return []
        
        results = [None] * len(texts)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Soumettre toutes les tâches
            future_to_index = {
                executor.submit(self.translate_with_retry, text): i
                for i, text in enumerate(texts)
            }
            
            # Collecter les résultats dans l'ordre
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    logging.error(f"Erreur traduction batch index {index}: {e}")
                    results[index] = texts[index]  # Fallback au texte original
        
        return results
    
    def get_cache_stats(self) -> Dict:
        """Retourne les statistiques combinées."""
        cache_stats = self.cache.get_stats()
        hit_rate = (self.stats['cache_hits'] / max(self.stats['translations_requested'], 1)) * 100
        
        return {
            'service_stats': self.stats,
            'cache_stats': cache_stats,
            'cache_hit_rate': round(hit_rate, 1)
        }
    
    def cleanup_cache(self) -> int:
        """Nettoie le cache expiré."""
        return self.cache.cleanup_expired()

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
        (self.output_dir / 'cache').mkdir(exist_ok=True)
        
        self.special_tokens = SpecialTokens()
        
        # Service de traduction amélioré avec cache et retry
        self.translation_service = EnhancedTranslationService(self.output_dir / 'cache')
        
        # Patterns regex pré-compilés pour l'optimisation
        self._compiled_patterns = self._compile_extraction_patterns()
        
        # Initialisation du modèle Hugging Face pour l'analyse de texte
        try:
            self.text_classifier = pipeline(
                "text-classification",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                device=-1  # CPU
            )
            logging.info("Modèle Hugging Face chargé avec succès")
        except Exception as e:
            logging.warning(f"Modèle Hugging Face non disponible: {e}")
            logging.info("Continuera sans analyse de sentiment avancée")
            self.text_classifier = None
    
    def _compile_extraction_patterns(self) -> List[re.Pattern]:
        """Compile les patterns regex pour l'extraction pour optimiser les performances."""
        patterns = [
            rb'[\x20-\x7E\x80-\xFF]{8,}',  # Chaînes ASCII étendues
            rb'[\x20-\x7E]{4,}',           # Chaînes ASCII standard
        ]
        return [re.compile(pattern) for pattern in patterns]

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
        Traite automatiquement tous les fichiers prometteurs du répertoire avec parallélisation.
        
        Args:
            test_mode: Si True, teste les méthodes de réinsertion avant application
            min_score: Score minimum pour considérer un fichier comme prometteur
        """
        logging.info("🚀 Début du traitement automatique optimisé...")
        
        # Analyser tous les fichiers
        if not self.analysis_report:
            self.analyze_all_files()
        
        # Obtenir les fichiers prometteurs
        promising_files = self.get_promising_files(min_score)
        
        if not promising_files:
            print("❌ Aucun fichier prometteur détecté.")
            return
        
        print(f"📁 {len(promising_files)} fichier(s) sélectionné(s) pour traitement")
        
        # Nettoyage du cache avant le début
        expired_count = self.translation_service.cleanup_cache()
        if expired_count > 0:
            print(f"🧹 {expired_count} entrée(s) expirée(s) supprimée(s) du cache")
        
        # Statistiques
        processed_count = 0
        error_count = 0
        test_results = {}
        
        # Mode parallélisé pour les gros volumes
        if len(promising_files) > 5:
            print("⚡ Mode parallélisé activé pour optimiser les performances")
            
            def process_single_file(file_path):
                """Fonction worker pour le traitement parallèle."""
                try:
                    file_format, confidence = self.file_analyzer.detect_file_format(file_path)
                    
                    if test_mode:
                        test_result = self.reinsertion_manager.test_reinsertion_methods(file_path, self)
                        if not test_result['success']:
                            return False, f"Aucune méthode de réinsertion trouvée"
                    
                    strategy = self.reinsertion_manager.choose_strategy(file_format, file_path, test_mode)
                    success = self.process_file_with_strategy(file_path, strategy)
                    
                    return success, "Succès" if success else "Échec"
                    
                except Exception as e:
                    return False, str(e)
            
            # Traitement parallèle avec ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as executor:  # Limiter à 2 workers pour éviter la saturation API
                future_to_file = {
                    executor.submit(process_single_file, file_path): file_path
                    for file_path in promising_files
                }
                
                for i, future in enumerate(as_completed(future_to_file), 1):
                    file_path = future_to_file[future]
                    print(f"\n📄 [{i}/{len(promising_files)}] {file_path.name}")
                    
                    try:
                        success, message = future.result()
                        if success:
                            processed_count += 1
                            print(f"  ✅ {message}")
                        else:
                            error_count += 1
                            print(f"  ❌ {message}")
                    except Exception as e:
                        error_count += 1
                        print(f"  ❌ Erreur: {e}")
        else:
            # Mode séquentiel pour les petits volumes
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
        
        # Rapport final avec statistiques du cache
        print(f"\n📈 RÉSUMÉ DU TRAITEMENT AUTOMATIQUE")
        print("=" * 40)
        print(f"✅ Fichiers traités avec succès: {processed_count}")
        print(f"❌ Fichiers en erreur: {error_count}")
        print(f"📊 Taux de réussite: {processed_count/(processed_count+error_count)*100:.1f}%")
        
        # Statistiques du cache
        cache_stats = self.translation_service.get_cache_stats()
        print(f"\n💾 STATISTIQUES DU CACHE:")
        print(f"📈 Taux de hit: {cache_stats['cache_hit_rate']:.1f}%")
        print(f"🏪 Entrées totales: {cache_stats['cache_stats']['total_entries']}")
        print(f"🔄 Hits totaux: {cache_stats['cache_stats']['total_hits']}")
        
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
        Extraction optimisée des textes avec patterns pré-compilés.
        """
        # Nouveau système: pas de vérification d'extension, on teste tous les fichiers
        out_json = self.output_dir / 'extracted' / (file_path.stem + '.json')

        try:
            with open(file_path, 'rb') as f:
                data = f.read()

            messages = []
            texts = []
            
            # Utiliser les patterns pré-compilés pour optimiser les performances
            all_matches = set()
            for pattern in self._compiled_patterns:
                matches = pattern.finditer(data)
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
        Traduit les textes avec le service amélioré (cache, retry, parallélisation).
        """
        import time
        import json
        import re
        import sys

        # Liste blanche personnalisable de noms propres à ne jamais traduire
        whitelist = [
            "Yukari", "Mitsuru", "Fuuka", "Akihiko", "Tartarus", "Nyx", "SEES", "Aigis", "Junpei", "Shinjiro", "Koromaru", "Elizabeth", "Igor", "Pharos", "Ryoji", "Chidori", "Strega", "Ikutsuki", "Takaya", "Jin", "Ken", "Persona", "Evoker", "S.E.E.S.", "Aragaki", "Makoto", "Minato", "Protagonist", "Yamagishi", "Sanada", "Takeba", "Iori", "Amada", "Tanaka", "Velvet Room", "Paulownia Mall", "Gekkoukan", "Mitsuru Kirijo", "Yukari Takeba", "Fuuka Yamagishi", "Akihiko Sanada", "Junpei Iori", "Shinjiro Aragaki", "Ken Amada", "Koromaru", "Aigis", "Elizabeth", "Igor", "Pharos", "Ryoji Mochizuki", "Chidori", "Takaya", "Jin", "Ikutsuki", "Strega", "Nyx Avatar", "Nyx", "Tartarus", "SEES", "Persona", "Evoker", "S.E.E.S."
        ]

        # Filtrer les textes à traduire
        texts_to_translate = []
        skip_indices = []
        
        for i, text in enumerate(texts):
            # Extraction des tokens et du texte propre
            tokens, clean_text = self.special_tokens.extract_game_tokens(text)
            
            # Récupération du contexte
            previous_text = texts[i-1] if i > 0 else None
            next_text = texts[i+1] if i < len(texts)-1 else None
            
            if not clean_text.strip() or self.should_skip_translation(text, whitelist, previous_text, next_text):
                skip_indices.append(i)
            else:
                texts_to_translate.append((i, clean_text, tokens))
        
        # Traduction par batch avec le service amélioré
        print(f"🔄 Traduction de {len(texts_to_translate)} textes (cache activé)...")
        
        if texts_to_translate:
            # Extraire seulement les textes propres pour la traduction
            clean_texts = [item[1] for item in texts_to_translate]
            
            # Utiliser la traduction par batch pour l'efficacité
            if len(clean_texts) > 10:  # Batch seulement si assez de textes
                translated_clean = self.translation_service.translate_batch(clean_texts, max_workers=3)
            else:
                # Traduction séquentielle pour les petits lots
                translated_clean = []
                for i, clean_text in enumerate(clean_texts, 1):
                    self.print_progress(i, len(clean_texts), clean_text)
                    translated = self.translation_service.translate_with_retry(clean_text)
                    translated_clean.append(translated)
                    time.sleep(0.1)  # Petite pause pour éviter les limitations
        else:
            translated_clean = []
        
        # Reconstruction des textes complets avec tokens
        translated = texts.copy()  # Commencer par copier tous les textes originaux
        
        for j, (original_index, _, tokens) in enumerate(texts_to_translate):
            if j < len(translated_clean):
                # Reconstruire avec les tokens originaux
                reconstructed = self.special_tokens.reconstruct_text(translated_clean[j], tokens)
                translated[original_index] = reconstructed
        
        print()  # Nouvelle ligne après la progression
        
        # Afficher les statistiques du cache
        stats = self.translation_service.get_cache_stats()
        print(f"📊 Cache: {stats['cache_hit_rate']:.1f}% hits, "
              f"{stats['cache_stats']['total_entries']} entrées")

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
        Valide la qualité de l'intégration après réinsertion avec suggestions détaillées.
        Retourne un rapport détaillé.
        """
        try:
            # Extraire les textes du fichier modifié
            new_texts = self.extract_texts(file_path)
            
            # Analyser le statut de traduction
            translation_status = self.file_analyzer.detect_translation_status(file_path)
            
            # Statistiques de base
            validation_report = {
                'file': str(file_path),
                'texts_found': len(new_texts) if new_texts else 0,
                'translation_status': translation_status['status'],
                'french_ratio': translation_status['confidence'],
                'quality_score': 0.0,
                'recommendations': [],
                'detailed_analysis': {},
                'suggestions': []
            }
            
            if new_texts and len(new_texts) > 0:
                # Analyse détaillée de la qualité
                french_count = translation_status.get('french_indicators', 0)
                english_count = translation_status.get('english_indicators', 0)
                total_indicators = french_count + english_count
                
                # Calcul du score de qualité
                if total_indicators > 0:
                    french_ratio = french_count / total_indicators
                    validation_report['quality_score'] = french_ratio
                    
                    # Analyse détaillée
                    validation_report['detailed_analysis'] = {
                        'french_indicators': french_count,
                        'english_indicators': english_count,
                        'total_texts': len(new_texts),
                        'translation_coverage': french_ratio,
                        'estimated_completion': min(100, french_ratio * 100)
                    }
                    
                    # Recommandations basées sur la qualité
                    if french_ratio >= 0.9:
                        validation_report['recommendations'].append("🌟 Excellente qualité - Traduction quasi-complète")
                        validation_report['suggestions'].append("Considérez ce fichier comme terminé")
                    elif french_ratio >= 0.7:
                        validation_report['recommendations'].append("✅ Très bonne qualité de traduction")
                        validation_report['suggestions'].append("Quelques textes pourraient nécessiter une révision")
                    elif french_ratio >= 0.5:
                        validation_report['recommendations'].append("✅ Bonne qualité de traduction")
                        validation_report['suggestions'].append("Re-traitement recommandé pour améliorer la couverture")
                    elif french_ratio >= 0.3:
                        validation_report['recommendations'].append("⚠️ Traduction partielle détectée")
                        validation_report['suggestions'].append("Vérifiez les paramètres d'extraction et de réinsertion")
                    elif french_ratio >= 0.1:
                        validation_report['recommendations'].append("❌ Peu de traductions détectées")
                        validation_report['suggestions'].append("Le fichier pourrait nécessiter un traitement spécialisé")
                    else:
                        validation_report['recommendations'].append("❌ Traduction non détectée")
                        validation_report['suggestions'].append("Vérifiez la compatibilité du format de fichier")
                    
                    # Suggestions spécifiques selon le ratio
                    if english_count > french_count * 2:
                        validation_report['suggestions'].append("Nombreux textes anglais restants - considérez un re-traitement")
                    
                    if french_count > 0 and english_count == 0:
                        validation_report['suggestions'].append("Traduction complète détectée - excellent travail!")
                    
                    # Analyse de la longueur des textes
                    if new_texts:
                        avg_length = sum(len(text) for text in new_texts) / len(new_texts)
                        validation_report['detailed_analysis']['average_text_length'] = avg_length
                        
                        if avg_length < 5:
                            validation_report['suggestions'].append("Textes très courts - possibles codes ou identifiants")
                        elif avg_length > 100:
                            validation_report['suggestions'].append("Textes longs détectés - vérifiez l'intégrité")
                
                else:
                    validation_report['recommendations'].append("ℹ️ Aucun indicateur de langue détecté")
                    validation_report['suggestions'].append("Fichier peut ne pas contenir de texte traduisible")
            else:
                validation_report['recommendations'].append("⚠️ Aucun texte extrait du fichier")
                validation_report['suggestions'].append("Vérifiez le format et la compatibilité du fichier")
            
            # Analyse de la taille du fichier
            file_size = file_path.stat().st_size
            validation_report['file_size'] = file_size
            validation_report['detailed_analysis']['file_size_kb'] = file_size // 1024
            
            if file_size > 1024 * 1024:  # > 1MB
                validation_report['recommendations'].append(f"📊 Fichier volumineux: {file_size // 1024}KB")
                validation_report['suggestions'].append("Expansion réussie - traductions longues intégrées")
            elif file_size > 100 * 1024:  # > 100KB
                validation_report['suggestions'].append("Taille normale pour un fichier de jeu")
            else:
                validation_report['suggestions'].append("Fichier petit - peut contenir peu de texte")
            
            # Score global basé sur plusieurs facteurs
            size_factor = min(1.0, file_size / (100 * 1024))  # Normaliser sur 100KB
            text_factor = min(1.0, len(new_texts) / 10) if new_texts else 0  # Normaliser sur 10 textes
            
            final_score = (
                validation_report['quality_score'] * 0.6 +  # 60% qualité traduction
                size_factor * 0.2 +                         # 20% taille fichier
                text_factor * 0.2                           # 20% nombre de textes
            )
            validation_report['quality_score'] = round(final_score, 3)
            
            return validation_report
            
        except Exception as e:
            return {
                'file': str(file_path),
                'error': str(e),
                'quality_score': 0.0,
                'recommendations': [f"❌ Erreur de validation: {e}"],
                'suggestions': ["Vérifiez l'intégrité du fichier et les permissions"],
                'detailed_analysis': {'error': True}
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

class P3FESTranslatorGUI:
    """Interface graphique simple pour le traducteur."""
    
    def __init__(self):
        if not GUI_AVAILABLE:
            raise ImportError("Interface graphique non disponible")
        
        self.root = tk.Tk()
        self.root.title("Persona 3 FES - Traducteur Français")
        self.root.geometry("800x600")
        
        self.translator = None
        self.processing = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """Configure l'interface utilisateur."""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configuration des chemins
        paths_frame = ttk.LabelFrame(main_frame, text="Configuration des chemins", padding="10")
        paths_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(paths_frame, text="Dossier du jeu:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.game_dir_var = tk.StringVar(value="GameFiles")
        ttk.Entry(paths_frame, textvariable=self.game_dir_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(paths_frame, text="Parcourir", command=self.browse_game_dir).grid(row=0, column=2)
        
        ttk.Label(paths_frame, text="Dossier de sortie:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_dir_var = tk.StringVar(value="TranslatedFiles")
        ttk.Entry(paths_frame, textvariable=self.output_dir_var, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(paths_frame, text="Parcourir", command=self.browse_output_dir).grid(row=1, column=2)
        
        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.test_mode_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Mode test (recommandé)", variable=self.test_mode_var).grid(row=0, column=0, sticky=tk.W)
        
        self.parallel_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Mode parallélisé", variable=self.parallel_var).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(options_frame, text="Score minimum:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.min_score_var = tk.DoubleVar(value=0.4)
        ttk.Scale(options_frame, from_=0.1, to=1.0, variable=self.min_score_var, orient=tk.HORIZONTAL).grid(row=1, column=1, sticky=(tk.W, tk.E))
        self.score_label = ttk.Label(options_frame, text="0.4")
        self.score_label.grid(row=1, column=2)
        
        self.min_score_var.trace('w', self.update_score_label)
        
        # Boutons d'action
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(buttons_frame, text="Analyser les fichiers", command=self.analyze_files).grid(row=0, column=0, padx=5)
        ttk.Button(buttons_frame, text="Traitement automatique", command=self.auto_process).grid(row=0, column=1, padx=5)
        ttk.Button(buttons_frame, text="Voir le progrès", command=self.show_progress).grid(row=0, column=2, padx=5)
        ttk.Button(buttons_frame, text="Stats du cache", command=self.show_cache_stats).grid(row=0, column=3, padx=5)
        
        # Zone de texte pour les logs
        log_frame = ttk.LabelFrame(main_frame, text="Journal", padding="5")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_text = tk.Text(log_frame, height=15, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Barre de progression
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Prêt")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # Configuration de la grille
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        paths_frame.columnconfigure(1, weight=1)
        options_frame.columnconfigure(1, weight=1)
    
    def update_score_label(self, *args):
        """Met à jour l'affichage du score."""
        self.score_label.config(text=f"{self.min_score_var.get():.1f}")
    
    def browse_game_dir(self):
        """Sélectionne le dossier du jeu."""
        dir_path = filedialog.askdirectory(title="Sélectionner le dossier du jeu")
        if dir_path:
            self.game_dir_var.set(dir_path)
    
    def browse_output_dir(self):
        """Sélectionne le dossier de sortie."""
        dir_path = filedialog.askdirectory(title="Sélectionner le dossier de sortie")
        if dir_path:
            self.output_dir_var.set(dir_path)
    
    def log(self, message):
        """Ajoute un message au journal."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def get_translator(self):
        """Obtient une instance du traducteur."""
        if not self.translator:
            self.translator = P3FESTranslator(self.game_dir_var.get(), self.output_dir_var.get())
        return self.translator
    
    def analyze_files(self):
        """Lance l'analyse des fichiers."""
        if self.processing:
            return
        
        self.processing = True
        self.status_var.set("Analyse en cours...")
        self.progress_var.set(0)
        
        try:
            translator = self.get_translator()
            self.log("🔍 Début de l'analyse des fichiers...")
            
            analysis_report = translator.analyze_all_files()
            
            # Afficher les résultats
            self.log(f"📊 Analyse terminée !")
            self.log(f"📁 Fichiers analysés: {analysis_report['analyzed_files']}")
            self.log(f"🎯 Fichiers à traiter: {len(analysis_report['untranslated_files'])}")
            self.log(f"✅ Fichiers traduits: {len(analysis_report['translated_files'])}")
            
            summary = analysis_report['translation_summary']
            if summary['fully_translated'] > 0:
                progress = (summary['fully_translated'] / analysis_report['analyzed_files']) * 100
                self.progress_var.set(progress)
                self.log(f"📈 Progrès: {progress:.1f}%")
            
            self.status_var.set("Analyse terminée")
            
        except Exception as e:
            self.log(f"❌ Erreur: {e}")
            messagebox.showerror("Erreur", f"Erreur lors de l'analyse: {e}")
        finally:
            self.processing = False
    
    def auto_process(self):
        """Lance le traitement automatique."""
        if self.processing:
            return
        
        if not messagebox.askyesno("Confirmation", "Lancer le traitement automatique ?"):
            return
        
        self.processing = True
        self.status_var.set("Traitement en cours...")
        
        try:
            translator = self.get_translator()
            self.log("🚀 Début du traitement automatique...")
            
            # Cette méthode devrait être adaptée pour utiliser des callbacks
            translator.auto_process_directory(
                test_mode=self.test_mode_var.get(),
                min_score=self.min_score_var.get()
            )
            
            self.log("✅ Traitement automatique terminé !")
            self.status_var.set("Traitement terminé")
            
        except Exception as e:
            self.log(f"❌ Erreur: {e}")
            messagebox.showerror("Erreur", f"Erreur lors du traitement: {e}")
        finally:
            self.processing = False
    
    def show_progress(self):
        """Affiche le progrès détaillé."""
        try:
            translator = self.get_translator()
            if not translator.analysis_report:
                translator.analyze_all_files()
            
            summary = translator.analysis_report['translation_summary']
            total = translator.analysis_report['analyzed_files']
            
            progress_text = f"📊 PROGRÈS DE TRADUCTION:\n"
            progress_text += f"📁 Total: {total} fichiers\n"
            progress_text += f"✅ Traduits: {summary['fully_translated']} ({summary['fully_translated']/total*100:.1f}%)\n"
            progress_text += f"🔶 Partiels: {summary['partially_translated']}\n"
            progress_text += f"❌ Non traduits: {summary['not_translated']}\n"
            
            messagebox.showinfo("Progrès de traduction", progress_text)
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")
    
    def show_cache_stats(self):
        """Affiche les statistiques du cache."""
        try:
            translator = self.get_translator()
            stats = translator.translation_service.get_cache_stats()
            
            stats_text = f"💾 STATISTIQUES DU CACHE:\n"
            stats_text += f"📊 Taux de hit: {stats['cache_hit_rate']:.1f}%\n"
            stats_text += f"🏪 Entrées: {stats['cache_stats']['total_entries']}\n"
            stats_text += f"🔄 Hits: {stats['cache_stats']['total_hits']}\n"
            stats_text += f"🆕 Récentes: {stats['cache_stats']['recent_entries']}\n"
            
            messagebox.showinfo("Statistiques du cache", stats_text)
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")
    
    def run(self):
        """Lance l'interface graphique."""
        self.log("🎮 Interface graphique du traducteur Persona 3 FES")
        self.log("💡 Sélectionnez les dossiers et cliquez sur 'Analyser les fichiers' pour commencer")
        self.root.mainloop()

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
    parser.add_argument('--gui', action='store_true', help='Lancer l\'interface graphique')
    
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
    parser.add_argument('--cache-stats', action='store_true', help='Affiche les statistiques du cache de traduction')
    parser.add_argument('--clean-cache', action='store_true', help='Nettoie le cache de traduction expiré')
    parser.add_argument('--parallel', action='store_true', help='Force le mode parallélisé même pour peu de fichiers')
    
    # Nouvelle option pour la stratégie de traduction
    parser.add_argument('--strategy', choices=['professional', 'preserve', 'mixed'], 
                       default='professional', 
                       help='Stratégie pour gérer les traductions trop longues (défaut: professional)')
    parser.add_argument('--show-strategies', action='store_true', 
                       help='Affiche les stratégies disponibles et leurs descriptions')
    
    args = parser.parse_args()
    
    # Interface graphique
    if args.gui:
        if not GUI_AVAILABLE:
            print("❌ Interface graphique non disponible (tkinter manquant)")
            sys.exit(1)
        
        try:
            app = P3FESTranslatorGUI()
            app.run()
            return
        except Exception as e:
            print(f"❌ Erreur interface graphique: {e}")
            sys.exit(1)
    
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
    parser.add_argument('--cache-stats', action='store_true', help='Affiche les statistiques du cache de traduction')
    parser.add_argument('--clean-cache', action='store_true', help='Nettoie le cache de traduction expiré')
    parser.add_argument('--parallel', action='store_true', help='Force le mode parallélisé même pour peu de fichiers')
    
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
            
        elif args.cache_stats:
            # Affichage des statistiques du cache
            translator = P3FESTranslator(args.game_dir, args.output_dir)
            stats = translator.translation_service.get_cache_stats()
            
            print("💾 STATISTIQUES DU CACHE DE TRADUCTION")
            print("=" * 40)
            print(f"📊 Taux de hit: {stats['cache_hit_rate']:.1f}%")
            print(f"🏪 Entrées totales: {stats['cache_stats']['total_entries']}")
            print(f"🔄 Hits totaux: {stats['cache_stats']['total_hits']}")
            print(f"🆕 Entrées récentes (24h): {stats['cache_stats']['recent_entries']}")
            print(f"📈 Traductions demandées: {stats['service_stats']['translations_requested']}")
            print(f"✅ Traductions réussies: {stats['service_stats']['successful_translations']}")
            print(f"❌ Erreurs de traduction: {stats['service_stats']['translation_errors']}")
            
        elif args.clean_cache:
            # Nettoyage du cache
            translator = P3FESTranslator(args.game_dir, args.output_dir)
            cleaned = translator.translation_service.cleanup_cache()
            print(f"🧹 Cache nettoyé: {cleaned} entrée(s) expirée(s) supprimée(s)")
            
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