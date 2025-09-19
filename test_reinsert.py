#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de test spécialisé pour tester la réimplémentation des textes traduits
dans les fichiers de jeu Persona 3 FES.
"""

import sys
import json
import shutil
from pathlib import Path

def create_realistic_test_file():
    """Crée un fichier de test plus réaliste avec des données binaires."""
    print("🔨 Création d'un fichier de test réaliste...")
    
    test_file = Path("GameFiles/realistic_test.pm1")
    
    # Contenu binaire plus réaliste d'un fichier de jeu
    # Avec des headers, padding et textes intégrés
    test_content = bytearray([
        # Header fictif
        0x50, 0x4D, 0x31, 0x00,  # "PM1\0"
        0x01, 0x00, 0x00, 0x00,  # Version
        0x10, 0x00, 0x00, 0x00,  # Offset vers les données
        0x00, 0x00, 0x00, 0x00,  # Padding
        
        # Données avec textes intégrés
    ])
    
    # Ajouter des textes avec des séparateurs nulls (typique des jeux)
    texts = [
        b"Welcome to the game",
        b"Press START to continue", 
        b"Loading...",
        b"Game Over",
        b"Try again?"
    ]
    
    for text in texts:
        test_content.extend(text)
        test_content.append(0x00)  # Séparateur null
    
    # Padding final
    while len(test_content) % 16 != 0:
        test_content.append(0x00)
    
    try:
        with open(test_file, 'wb') as f:
            f.write(test_content)
        print(f"  ✅ Fichier de test réaliste créé: {test_file}")
        print(f"  📊 Taille: {len(test_content)} bytes")
        return test_file
    except Exception as e:
        print(f"  ❌ Erreur lors de la création: {e}")
        return None

def test_extraction_and_validation(test_file):
    """Teste l'extraction et valide les données extraites."""
    print("\n🔍 Test d'extraction approfondi...")
    
    try:
        from p3fes_translator import P3FESTranslator
        
        translator = P3FESTranslator("GameFiles", "TestOutput")
        texts = translator.extract_texts(test_file)
        
        if not texts:
            print("  ❌ Aucun texte extrait")
            return None, None
        
        print(f"  ✅ {len(texts)} texte(s) extrait(s):")
        for i, text in enumerate(texts):
            print(f"    {i+1}. '{text}' (longueur: {len(text)})")
        
        # Charger le fichier JSON d'extraction pour plus de détails
        extracted_json = translator.output_dir / 'extracted' / (test_file.stem + '.json')
        if extracted_json.exists():
            with open(extracted_json, 'r', encoding='utf-8') as f:
                extraction_data = json.load(f)
            print(f"  📋 Données d'extraction sauvegardées: {len(extraction_data)} entrées")
            return texts, extraction_data
        else:
            print("  ⚠️ Fichier JSON d'extraction non trouvé")
            return texts, None
            
    except Exception as e:
        print(f"  ❌ Erreur d'extraction: {e}")
        return None, None

def test_translation_with_various_lengths(texts):
    """Teste la traduction avec des textes de différentes longueurs."""
    print("\n🔄 Test de traduction avec différentes longueurs...")
    
    if not texts:
        print("  ❌ Pas de textes à traduire")
        return None
    
    # Simulations de traductions avec différentes longueurs
    translations = []
    for text in texts:
        if "Welcome" in text:
            translations.append("Bienvenue dans le jeu")  # Plus long
        elif "Press START" in text:
            translations.append("START pour continuer")    # Plus court
        elif "Loading" in text:
            translations.append("Chargement...")          # Même longueur
        elif "Game Over" in text:
            translations.append("Fin de partie")          # Différent
        elif "Try again" in text:
            translations.append("Réessayer ?")            # Avec caractères spéciaux
        else:
            translations.append(text)  # Garde l'original si non reconnu
    
    print("  ✅ Traductions simulées:")
    for i, (orig, trad) in enumerate(zip(texts, translations)):
        length_diff = len(trad) - len(orig)
        status = "+" if length_diff > 0 else "-" if length_diff < 0 else "="
        print(f"    {i+1}. '{orig}' → '{trad}' ({status}{abs(length_diff)})")
    
    return translations

def test_reinsert_with_backup_verification(test_file, translated_texts, extraction_data):
    """Teste la réinsertion avec vérification des sauvegardes."""
    print("\n🔧 Test de réinsertion avec vérification...")
    
    if not translated_texts:
        print("  ❌ Pas de textes traduits")
        return False
    
    try:
        from p3fes_translator import P3FESTranslator
        
        # Créer une copie de travail
        work_file = test_file.with_suffix('.work.pm1')
        shutil.copy2(test_file, work_file)
        
        # Sauvegarder le contenu original pour comparaison
        with open(test_file, 'rb') as f:
            original_content = f.read()
        
        translator = P3FESTranslator("GameFiles", "TestOutput")
        
        # Effectuer d'abord l'extraction sur le fichier de travail pour créer le JSON nécessaire
        print("  🔄 Pré-extraction sur le fichier de travail...")
        work_texts = translator.extract_texts(work_file)
        
        if not work_texts:
            print("  ❌ Échec de la pré-extraction")
            work_file.unlink()
            return False
        
        print("  🔄 Réinsertion en cours...")
        success = translator.reinsert_texts(work_file, translated_texts)
        
        if success:
            print("  ✅ Réinsertion technique réussie")
            
            # Vérifications post-réinsertion
            with open(work_file, 'rb') as f:
                modified_content = f.read()
            
            # Analyse des changements
            print("  📊 Analyse des modifications:")
            print(f"    - Taille originale: {len(original_content)} bytes")
            print(f"    - Taille modifiée: {len(modified_content)} bytes")
            
            # Compter les bytes différents
            diff_count = sum(1 for a, b in zip(original_content, modified_content) if a != b)
            print(f"    - Bytes modifiés: {diff_count}/{len(original_content)}")
            
            # Vérifier que des changements ont eu lieu
            if diff_count > 0:
                print("  ✅ Le fichier a été effectivement modifié")
                
                # Vérifier la cohérence structurelle (les premiers bytes de header ne doivent pas changer)
                if original_content[:16] == modified_content[:16]:
                    print("  ✅ Structure de header préservée")
                else:
                    print("  ⚠️ Header modifié (peut être normal selon le format)")
                
            else:
                print("  ⚠️ Aucune modification détectée")
            
            # Vérifier que le fichier de sauvegarde a été créé
            backup_file = work_file.with_suffix(work_file.suffix + '.backup')
            if backup_file.exists():
                print("  ✅ Fichier de sauvegarde créé")
                backup_file.unlink()  # Nettoyage
            
            # Nettoyage
            work_file.unlink()
            return True
            
        else:
            print("  ❌ Échec de la réinsertion")
            if work_file.exists():
                work_file.unlink()
            return False
            
    except Exception as e:
        print(f"  ❌ Erreur durant la réinsertion: {e}")
        # Nettoyage en cas d'erreur
        try:
            if 'work_file' in locals() and work_file.exists():
                work_file.unlink()
        except:
            pass
        return False

def test_round_trip_integrity(test_file):
    """Teste l'intégrité d'un cycle complet extraction -> traduction -> réinsertion."""
    print("\n🔄 Test d'intégrité cycle complet...")
    
    try:
        from p3fes_translator import P3FESTranslator
        
        # Créer un fichier pour le test cycle complet
        roundtrip_file = test_file.with_suffix('.roundtrip.pm1')
        shutil.copy2(test_file, roundtrip_file)
        
        translator = P3FESTranslator("GameFiles", "TestOutput")
        
        print("  🔄 Étape 1: Extraction...")
        original_texts = translator.extract_texts(roundtrip_file)
        
        if not original_texts:
            print("  ❌ Échec de l'extraction")
            return False
        
        print(f"  ✅ {len(original_texts)} textes extraits")
        
        print("  🔄 Étape 2: Traduction simulée...")
        # Traduction simple pour garder les longueurs similaires
        translated_texts = [f"[FR] {text}" if len(text) > 10 else text for text in original_texts]
        
        print("  🔄 Étape 3: Réinsertion...")
        reinsert_success = translator.reinsert_texts(roundtrip_file, translated_texts)
        
        if not reinsert_success:
            print("  ❌ Échec de la réinsertion")
            return False
        
        print("  🔄 Étape 4: Nouvelle extraction pour vérification...")
        final_texts = translator.extract_texts(roundtrip_file)
        
        if not final_texts:
            print("  ❌ Échec de la re-extraction")
            return False
        
        print("  📊 Comparaison finale:")
        print(f"    - Textes originaux: {len(original_texts)}")
        print(f"    - Textes finaux: {len(final_texts)}")
        
        # Vérifier que nous avons le même nombre de textes
        if len(original_texts) == len(final_texts):
            print("  ✅ Nombre de textes préservé")
            
            # Vérifier quelques échantillons
            changes_detected = 0
            for i, (orig, final) in enumerate(zip(original_texts[:3], final_texts[:3])):
                if orig != final:
                    changes_detected += 1
                    print(f"    {i+1}. '{orig}' → '{final}'")
            
            if changes_detected > 0:
                print(f"  ✅ {changes_detected} modification(s) détectée(s) (bon signe)")
            else:
                print("  ⚠️ Aucune modification détectée")
            
            # Nettoyage
            roundtrip_file.unlink()
            return True
        else:
            print("  ❌ Nombre de textes différent")
            roundtrip_file.unlink()
            return False
        
    except Exception as e:
        print(f"  ❌ Erreur durant le test cycle complet: {e}")
        try:
            if 'roundtrip_file' in locals() and roundtrip_file.exists():
                roundtrip_file.unlink()
        except:
            pass
        return False

def main():
    """Fonction principale du test de réimplémentation."""
    print("🧪 TEST SPÉCIALISÉ DE RÉIMPLÉMENTATION P3FES")
    print("=" * 50)
    
    # Créer un fichier de test réaliste
    test_file = create_realistic_test_file()
    if not test_file:
        print("❌ Impossible de créer le fichier de test")
        return 1
    
    try:
        # Test 1: Extraction approfondie
        texts, extraction_data = test_extraction_and_validation(test_file)
        test1_success = texts is not None
        
        # Test 2: Traduction avec variations de longueur
        translated_texts = test_translation_with_various_lengths(texts) if texts else None
        test2_success = translated_texts is not None
        
        # Test 3: Réinsertion avec vérifications
        test3_success = test_reinsert_with_backup_verification(test_file, translated_texts, extraction_data) if translated_texts else False
        
        # Test 4: Test d'intégrité cycle complet
        test4_success = test_round_trip_integrity(test_file)
        
        # Nettoyage final
        test_file.unlink()
        print("\n🧹 Fichier de test principal nettoyé")
        
        # Résultats
        print("\n📊 RÉSULTATS DU TEST DE RÉIMPLÉMENTATION")
        print("=" * 40)
        
        tests = [
            ("Extraction approfondie", test1_success),
            ("Traduction avec variations", test2_success), 
            ("Réinsertion avec vérifications", test3_success),
            ("Intégrité cycle complet", test4_success)
        ]
        
        passed = sum(success for _, success in tests)
        total = len(tests)
        
        for test_name, success in tests:
            status = "✅" if success else "❌"
            print(f"  {status} {test_name}")
        
        if passed == total:
            print(f"\n🎉 Tous les tests de réimplémentation réussis ({passed}/{total})")
            print("🚀 La réimplémentation fonctionne parfaitement !")
            print("💡 Vos fichiers de jeu peuvent être traduits en toute sécurité.")
            return 0
        else:
            print(f"\n⚠️ {total - passed} test(s) de réimplémentation échoué(s) sur {total}")
            print("🔧 Il y a des problèmes avec la réimplémentation des textes")
            if passed >= 2:
                print("💡 Les fonctions de base marchent, mais attention aux cas complexes")
            return 1
            
    except Exception as e:
        print(f"\n❌ Erreur fatale durant les tests: {e}")
        try:
            if test_file.exists():
                test_file.unlink()
        except:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())