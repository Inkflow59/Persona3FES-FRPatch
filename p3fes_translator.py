#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
import shutil
from datetime import datetime
from deep_translator import GoogleTranslator
from googletrans import Translator as PyGoogleTranslator
import requests
import time
import re
import sys
import subprocess
from dotenv import load_dotenv

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
        
        # Création des répertoires nécessaires
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / 'extracted').mkdir(exist_ok=True)
        (self.output_dir / 'translated').mkdir(exist_ok=True)
        
        self.special_tokens = SpecialTokens()
        
        # Initialisation du traducteur de secours
        self.backup_translator = PyGoogleTranslator()

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
    
    def extract_texts(self, file_path: Path) -> Optional[List[str]]:
        """
        Extraction unifiée des textes pour tous les formats supportés.
        Les textes sont extraits avec leur contexte (offset, tokens, etc.) et sauvegardés en .json.
        """
        extension = file_path.suffix.lower()
        if extension not in self.supported_extensions:
            logging.warning(f"Extension non supportée: {extension} pour {file_path}")
            return None

        extracted = []
        out_json = self.output_dir / 'extracted' / (file_path.stem + '.json')

        try:
            with open(file_path, 'rb') as f:
                data = f.read()

            # Pattern commun pour tous les formats : recherche de chaînes imprimables
            pattern = rb'[\x20-\x7E]{4,}'
            matches = re.findall(pattern, data)
            
            messages = []
            for i, match in enumerate(matches):
                try:
                    text = match.decode('shift_jis')
                    if len(text.strip()) >= 4:
                        # Calcul de l'offset pour chaque texte trouvé
                        offset = data.find(match)
                        messages.append({
                            'offset': offset,
                            'raw': match.hex(),
                            'texts': [text.strip()]
                        })
                except Exception:
                    continue

            # Sauvegarde des messages extraits
            with open(out_json, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            
            logging.info(f"{len(messages)} messages extraits de {file_path}")
            return [t for msg in messages for t in msg['texts']]

        except Exception as e:
            logging.error(f"Erreur extraction {extension}: {e}")
            return None

    def translate_with_backup(self, text: str) -> str:
        """Traduit un texte avec py-googletrans comme solution de secours."""
        try:
            result = self.backup_translator.translate(text, src='en', dest='fr')
            return result.text
        except Exception as e:
            logging.error(f"Erreur lors de la traduction avec py-googletrans: {e}")
            return text

    def is_valid_sentence(self, text: str) -> bool:
        """
        Analyse si une phrase est valide pour la traduction.
        """
        # Nettoyage du texte
        text = text.strip()
        
        # Critères de base
        if not text or len(text) < 3:
            return False
        
        # Vérification de la structure grammaticale basique
        words = text.split()
        if len(words) < 2:  # Au moins 2 mots
            return False
        
        # Vérification de la ponctuation
        has_punctuation = any(c in text for c in '.!?,;:')
        
        # Vérification de la casse
        has_proper_case = any(c.isupper() for c in text) and not text.isupper()
        
        # Vérification des caractères spéciaux
        special_chars = re.findall(r'[^a-zA-Z0-9\s.,!?;:\'\"-]', text)
        if len(special_chars) > len(text) * 0.3:  # Plus de 30% de caractères spéciaux
            return False
        
        # Vérification de la cohérence des espaces
        if '  ' in text or text.startswith(' ') or text.endswith(' '):
            return False
        
        return has_punctuation or has_proper_case

    def analyze_context(self, text: str, previous_text: str = None, next_text: str = None) -> bool:
        """
        Analyse le contexte d'une phrase pour déterminer si elle doit être traduite.
        """
        # Si le texte précédent ou suivant est un code technique, on peut ignorer
        if previous_text and re.match(r'^[A-Z0-9_]+$', previous_text):
            return False
        if next_text and re.match(r'^[A-Z0-9_]+$', next_text):
            return False
        
        # Si le texte est entouré de guillemets, c'est probablement un dialogue
        if text.startswith('"') and text.endswith('"'):
            return True
        
        # Si le texte est entouré de parenthèses, c'est probablement une note
        if text.startswith('(') and text.endswith(')'):
            return True
        
        return True

    def should_skip_translation(self, text: str, whitelist: List[str], previous_text: str = None, next_text: str = None) -> bool:
        # Extraction des tokens et du texte propre
        tokens, clean_text = self.special_tokens.extract_game_tokens(text)
        
        # Si le texte ne contient que des tokens spéciaux
        if not clean_text.strip():
            return True
        
        # Patterns à ignorer
        skip_patterns = [
            r'^\d+$',  # Nombres seuls
            r'^[A-Z0-9_]+$',  # Codes techniques
            r'^[A-Z]{2,}$',  # Acronymes
            r'^[a-z]+$',  # Mots en minuscules seuls
            r'^[A-Z][a-z]+$',  # Noms propres simples
            r'^[A-Z][a-z]+\s+[A-Z][a-z]+$',  # Noms composés
            r'^[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+$',  # Noms triples
            r'^[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+$',  # Noms quadruples
        ]
        
        # Vérification des patterns
        for pattern in skip_patterns:
            if re.match(pattern, clean_text):
                return True
        
        # Vérification de la structure de la phrase
        if not self.is_valid_sentence(clean_text):
            return True
        
        # Vérification du contexte
        if not self.analyze_context(clean_text, previous_text, next_text):
            return True
        
        # Vérification des tokens spéciaux
        if self.special_tokens.is_special_token(clean_text):
            return True
        
        return False

    def print_progress(self, current: int, total: int, text: str):
        """Affiche la progression de la traduction avec le texte en cours."""
        progress = (current / total) * 100
        sys.stdout.write(f"\rTraduction en cours : {progress:.1f}% - Texte {current}/{total}: {text[:50]}...")
        sys.stdout.flush()

    def translate_texts(self, texts: List[str], file_path: Path = None) -> List[str]:
        """
        Traduit les textes de l'anglais vers le français avec Google Translator.
        En cas d'échec, utilise py-googletrans comme traducteur de secours.
        """
        import time
        import json
        import re
        import sys

        # Liste blanche personnalisable de noms propres à ne jamais traduire
        whitelist = [
            "Yukari", "Mitsuru", "Fuuka", "Akihiko", "Tartarus", "Nyx", "SEES", "Aigis", "Junpei", "Shinjiro", "Koromaru", "Elizabeth", "Igor", "Pharos", "Ryoji", "Chidori", "Strega", "Ikutsuki", "Takaya", "Jin", "Ken", "Persona", "Evoker", "S.E.E.S.", "Aragaki", "Makoto", "Minato", "Protagonist", "Yamagishi", "Sanada", "Takeba", "Iori", "Amada", "Tanaka", "Velvet Room", "Paulownia Mall", "Gekkoukan", "Mitsuru Kirijo", "Yukari Takeba", "Fuuka Yamagishi", "Akihiko Sanada", "Junpei Iori", "Shinjiro Aragaki", "Ken Amada", "Koromaru", "Aigis", "Elizabeth", "Igor", "Pharos", "Ryoji Mochizuki", "Chidori", "Takaya", "Jin", "Ikutsuki", "Strega", "Nyx Avatar", "Nyx", "Tartarus", "SEES", "Persona", "Evoker", "S.E.E.S."
        ]

        def is_proper_name(text, whitelist):
            if text in whitelist:
                return True
            # Si le texte commence par une majuscule et n'est pas tout en majuscules, et fait moins de 3 mots
            if text and text[0].isupper() and not text.isupper() and len(text.split()) <= 3:
                return True
            return False

        def is_normal_sentence(text):
            # Une phrase normalement constituée contient au moins un espace et n'est pas tout en majuscules ni un nom propre.
            if not text.strip():
                return False
            if text.isupper():
                return False
            if re.match(r'^MSG_\d+$', text):
                return False
            if " " not in text:
                return False
            return True

        translated = []
        
        try:
            # Initialisation du traducteur Google
            google_translator = GoogleTranslator(source='en', target='fr')
            
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
                    # Première tentative avec Google Translate
                    fr = google_translator.translate(clean_text)
                except Exception as e:
                    try:
                        # Tentative de secours avec py-googletrans
                        fr = self.translate_with_backup(clean_text)
                        if fr != text:  # Si la traduction a réussi
                            logging.info(f"py-googletrans a réussi à traduire le texte après échec de Google Translate")
                        else:
                            logging.warning("Échec de py-googletrans, retour au texte original")
                            fr = text
                    except Exception as e2:
                        logging.error(f"Échec des deux traducteurs sur '{text}': Google={e}, py-googletrans={e2}")
                        fr = text
                
                # Reconstruction avec les tokens originaux
                fr = self.special_tokens.reconstruct_text(fr, tokens)
                translated.append(fr)
                time.sleep(0.5)  # Pause pour respecter les limites d'API
            
            print()

        except Exception as e:
            logging.error(f"Erreur d'initialisation des traducteurs : {e}")
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
    
    def reinsert_texts(self, file_path: Path, translated_texts: List[str]) -> bool:
        """
        Réinsère les textes traduits dans le fichier original.
        Le fichier modifié est sauvegardé dans 'reinjected/' puis copié vers le fichier original.
        Met à jour le hash du fichier dans processed_files.json après l'écrasement.
        """
        import json
        import shutil
        extension = file_path.suffix.lower()
        output_dir = self.output_dir / 'reinjected'
        output_dir.mkdir(exist_ok=True)
        out_file = output_dir / file_path.name
        
        try:
            with open(file_path, 'rb') as f:
                data = bytearray(f.read())
                
            # PM1 : structure avancée avec offsets
            if extension == '.pm1':
                # On relit le json d'extraction avancée
                extracted_json = self.output_dir / 'extracted' / (file_path.stem + '.json')
                if not extracted_json.exists():
                    logging.error(f"Fichier d'extraction avancée manquant : {extracted_json}")
                    return False
                with open(extracted_json, 'r', encoding='utf-8') as f:
                    messages = json.load(f)
                if len(messages) != len(translated_texts):
                    logging.error(f"Nombre de textes traduits ({len(translated_texts)}) différent du nombre de messages extraits ({len(messages)})")
                    return False
                for msg, new_text in zip(messages, translated_texts):
                    chunk = bytearray.fromhex(msg['raw'])
                    # On cherche la/les chaînes originales dans le chunk
                    for old, _ in zip(msg['texts'], [new_text]*len(msg['texts'])):
                        try:
                            old_bytes = old.encode('shift_jis')
                        except Exception:
                            continue
                        idx = chunk.find(old_bytes)
                        if idx == -1:
                            continue
                        # Réencodage safe
                        try:
                            new_bytes = new_text.encode('shift_jis')
                        except Exception:
                            new_bytes = old_bytes
                        if len(new_bytes) > len(old_bytes):
                            # Tronque pour ne pas dépasser la taille d'origine
                            new_bytes = new_bytes[:len(old_bytes)]
                        elif len(new_bytes) < len(old_bytes):
                            # Pad avec des espaces (0x20)
                            new_bytes = new_bytes + b' ' * (len(old_bytes) - len(new_bytes))
                        chunk[idx:idx+len(old_bytes)] = new_bytes
                    # Remplace le chunk dans le fichier binaire
                    data[msg['offset']:msg['offset']+len(chunk)] = chunk
            # PAC/PAK/BF/TBL : remplacement simple des chaînes imprimables
            elif extension in {'.pac', '.pak', '.bf', '.tbl'}:
                # On relit les chaînes extraites
                extracted_json = self.output_dir / 'extracted' / (file_path.stem + '.json')
                if not extracted_json.exists():
                    logging.error(f"Fichier d'extraction manquant : {extracted_json}")
                    return False
                with open(extracted_json, 'r', encoding='utf-8') as f:
                    old_strings = json.load(f)
                if len(old_strings) != len(translated_texts):
                    logging.error(f"Nombre de textes traduits ({len(translated_texts)}) différent du nombre de chaînes extraites ({len(old_strings)})")
                    return False
                for old, new in zip(old_strings, translated_texts):
                    try:
                        old_bytes = old.encode('shift_jis')
                    except Exception:
                        continue
                    try:
                        new_bytes = new.encode('shift_jis')
                    except Exception:
                        new_bytes = old_bytes
                    if len(new_bytes) > len(old_bytes):
                        new_bytes = new_bytes[:len(old_bytes)]
                    elif len(new_bytes) < len(old_bytes):
                        new_bytes = new_bytes + b' ' * (len(old_bytes) - len(new_bytes))
                    idx = data.find(old_bytes)
                    if idx != -1:
                        data[idx:idx+len(old_bytes)] = new_bytes
            else:
                logging.warning(f"Réinsertion non implémentée pour {extension}")
                return False
            
            # Sauvegarde dans le dossier reinjected
            with open(out_file, 'wb') as f:
                f.write(data)
            logging.info(f"Fichier réinjecté sauvegardé : {out_file}")
            
            # Copie du fichier réinjecté vers le fichier original
            try:
                shutil.copy2(out_file, file_path)
                logging.info(f"Fichier original écrasé avec succès : {file_path}")
                
                # Mise à jour du hash après l'écrasement
                new_hash = self._calculate_file_hash(file_path)
                self.processed_files[str(file_path)] = new_hash
                self._save_processed_files()
                logging.info(f"Hash du fichier mis à jour dans processed_files.json")
                
            except Exception as e:
                logging.error(f"Erreur lors de l'écrasement du fichier original : {e}")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Erreur lors de la réinsertion : {e}")
            return False
    
    def process_file(self, file_path: Path) -> bool:
        """Traite un fichier complet (extraction, traduction, réinsertion)."""
        if not self._is_file_modified(file_path):
            logging.info(f"Fichier déjà traité et non modifié: {file_path}")
            return True
            
        try:
            texts = self.extract_texts(file_path)
            if texts is None:
                return False
                
            # Vérification si le fichier contient des textes à traduire
            if not texts:
                logging.info(f"Aucun texte à traduire trouvé dans {file_path}, fichier ignoré")
                # Enregistrer le fichier comme traité même s'il n'y a pas de textes
                self.processed_files[str(file_path)] = self._calculate_file_hash(file_path)
                self._save_processed_files()
                return True
                
            translated_texts = self.translate_texts(texts, file_path)
            if not self.reinsert_texts(file_path, translated_texts):
                return False
                
            # Mise à jour du hash du fichier
            self.processed_files[str(file_path)] = self._calculate_file_hash(file_path)
            self._save_processed_files()
            return True
            
        except Exception as e:
            logging.error(f"Erreur lors du traitement de {file_path}: {str(e)}")
            return False
    
    def process_directory(self):
        """Traite tous les fichiers du répertoire du jeu."""
        for root, _, files in os.walk(self.game_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.supported_extensions:
                    self.process_file(file_path)

def main():
    """Point d'entrée principal du programme."""
    game_dir = "GameFiles"  # À ajuster selon votre configuration
    output_dir = "TranslatedFiles"
    
    translator = P3FESTranslator(game_dir, output_dir)
    translator.process_directory()

if __name__ == "__main__":
    main()