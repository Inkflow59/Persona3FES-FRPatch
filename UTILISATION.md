# 🚀 GUIDE D'UTILISATION RAPIDE - VERSION 2.1

## 🔧 Installation

1. **Installer Python 3.8+** si ce n'est pas fait
2. **Installer les dépendances**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Optionnel**: Installer tkinter pour l'interface graphique:
   ```bash
   # Windows (déjà inclus normalement)
   # Ubuntu/Debian
   sudo apt-get install python3-tk
   ```

## 🎯 Préparation

1. **Créer le dossier GameFiles** (déjà fait)
2. **Copier vos fichiers** de Persona 3 FES dans `GameFiles/`
3. **Faire une sauvegarde** de vos fichiers originaux !

## 💻 Utilisation

### 🖥️ NOUVEAU! Interface Graphique
```bash
python p3fes_translator.py --gui
```
**Interface utilisateur simple et intuitive avec boutons, barres de progression et logs visuels.**

### 🔍 Mode Analyse Intelligente (recommandé en premier)
```bash
python p3fes_translator.py --analyze
```
**Détecte automatiquement les fichiers traduisibles et ceux déjà traduits.**

### 📋 Voir les fichiers restants
```bash
python p3fes_translator.py --remaining
```
**Affiche UNIQUEMENT les fichiers non traduits avec estimation du temps.**

### 🤖 Traduction automatique optimisée
```bash
python p3fes_translator.py --auto-test
```
**Mode intelligent avec cache, parallélisation et tests adaptatifs.**

### 📊 Suivi du progrès
```bash
python p3fes_translator.py --progress
```
**Barre de progression, statistiques et pourcentage de completion.**

### 💾 Gestion du cache
```bash
# Voir les statistiques du cache
python p3fes_translator.py --cache-stats

# Nettoyer le cache expiré
python p3fes_translator.py --clean-cache
```
**Cache intelligent qui évite les re-traductions et accélère le processus.**

### 🧪 Mode test (analyse sans modification)
```bash
python p3fes_translator.py --test
```
Affiche les textes qui seraient traduits sans les modifier.

### 📁 Traduction d'un fichier spécifique
```bash
python p3fes_translator.py --file GameFiles/MSG_001.pm1
```

### 🔧 Mode verbose (pour débogage)
```bash
python p3fes_translator.py --verbose --auto-test
```

## 🎯 Workflow Recommandé

```bash
# 1. Interface graphique (plus facile)
python p3fes_translator.py --gui

# OU workflow en ligne de commande:
# 1. Première analyse
python p3fes_translator.py --analyze

# 2. Voir ce qui reste à faire
python p3fes_translator.py --remaining

# 3. Traduction automatique optimisée
python p3fes_translator.py --auto-test

# 4. Vérifier le progrès
python p3fes_translator.py --progress

# 5. Répéter 3-4 jusqu'à 100%
```

## 📊 Nouvelles Fonctionnalités v2.1

### ⚡ Performances Optimisées
- **Cache SQLite intelligent** : Évite les re-traductions
- **Traduction par batch** : Parallélisation des requêtes
- **Patterns pré-compilés** : Extraction plus rapide
- **Mode parallélisé** : Traitement simultané de plusieurs fichiers

### 🛡️ Robustesse Améliorée
- **Retry automatique** : 3 tentatives avec backoff exponentiel
- **Gestion d'erreurs avancée** : Fallback au texte original
- **Validation intelligente** : Score de qualité avec suggestions
- **Sauvegarde automatique** : Protection des données

### 🖥️ Interface Utilisateur
- **GUI tkinter** : Interface graphique optionnelle
- **Barre de progression** : Suivi visuel en temps réel
- **Statistiques détaillées** : Cache, succès, erreurs
- **Logs intégrés** : Affichage des opérations en cours

## 📈 Résultats et Structure

### 📁 Structure Complète
```
Persona3FES-FRPatch/
├── GameFiles/          ← VOS FICHIERS ICI
├── TranslatedFiles/    ← Fichiers de travail (auto-créé)
│   ├── extracted/     ← Textes extraits en JSON
│   ├── translated/    ← Textes traduits en JSON
│   ├── reinjected/    ← Versions modifiées
│   ├── analysis/      ← 🆕 Rapports intelligents
│   └── cache/         ← 🆕 Cache de traduction SQLite
├── p3fes_translator.py ← Script principal amélioré
└── translation.log    ← Journal détaillé
```

### 📊 Données de Sortie
- **Fichiers traduits** : Originaux modifiés avec sauvegarde
- **Logs détaillés** : `translation.log` avec progression
- **Cache intelligent** : Base SQLite avec TTL (7 jours)
- **Rapports d'analyse** : JSON avec statistiques complètes
- **Statistiques temps réel** : Taux de cache, progression, etc.

## 🔧 Dépannage Avancé

| Problème | Solution Optimisée |
|----------|-------------------|
| "Aucun fichier trouvé" | `--analyze` pour détecter tous les formats |
| "Erreur d'extraction" | `--verbose` pour diagnostics détaillés |
| "Erreur de traduction" | Cache et retry automatiques intégrés |
| "Permission denied" | Mode administrateur ou dossier utilisateur |
| "Interface GUI manquante" | `pip install tk` ou mode ligne de commande |
| "Cache trop volumineux" | `--clean-cache` pour nettoyage automatique |
| "Traduction lente" | Cache accélère les reprises, mode `--parallel` |
| "Fichiers partiels" | `--remaining` montre exactement ce qui reste |

## 🌟 Avantages de la v2.1

✅ **3-5x plus rapide** grâce au cache et à la parallélisation  
✅ **Interface graphique** pour faciliter l'utilisation  
✅ **Reprise intelligente** - continue exactement où vous vous étiez arrêté  
✅ **Validation avancée** avec suggestions d'amélioration  
✅ **Gestion d'erreurs robuste** avec retry automatique  
✅ **Statistiques temps réel** pour suivre le progrès  
✅ **Cache persistant** évite les re-traductions  
✅ **Compatibilité 100%** avec l'utilisation précédente  

🚀 **Profitez de la traduction automatique nouvelle génération !**