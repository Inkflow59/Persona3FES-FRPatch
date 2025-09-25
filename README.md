# 🎮 Persona 3 FES - Patch de Traduction Française Intelligent v2.1

<div align="center">

![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)
![Licence](https://img.shields.io/badge/licence-MIT-yellow.svg)
![Statut](https://img.shields.io/badge/statut-stable-brightgreen.svg)
![IA](https://img.shields.io/badge/IA-Hugging%20Face-purple.svg)
![Traduction](https://img.shields.io/badge/traduction-automatique-orange.svg)
![Cache](https://img.shields.io/badge/cache-SQLite-red.svg)
![GUI](https://img.shields.io/badge/GUI-tkinter-green.svg)
![Performance](https://img.shields.io/badge/performance-3x%20plus%20rapide-gold.svg)

[English](README.md) | [Français](README.fr.md)

*Système intelligent de traduction automatique nouvelle génération avec cache SQLite, interface graphique, parallélisation et validation avancée*

</div>

## 📋 Table des matières

- [À propos](#-à-propos)
- [🌟 Nouveautés v2.0](#-nouveautés-v20)
- [✨ Fonctionnalités](#-fonctionnalités)
- [🚀 Installation](#-installation)
- [⚙️ Configuration](#️-configuration)
- [💻 Utilisation](#-utilisation)
- [📊 Modes d'analyse](#-modes-danalyse)
- [📁 Structure du projet](#-structure-du-projet)
- [🔧 Dépannage](#-dépannage)
- [🤝 Contribution](#-contribution)
- [📝 Licence](#-licence)

## 🎯 À propos

Ce projet révolutionne la traduction des fichiers de Persona 3 FES avec un système intelligent nouvelle génération. La version 2.1 apporte un **cache SQLite**, une **interface graphique**, une **parallélisation avancée** et des **performances 3-5x supérieures**. Il utilise l'IA, des algorithmes adaptatifs et un système de validation intelligent pour préserver parfaitement les tokens spéciaux du jeu tout en assurant une traduction de qualité professionnelle avec suivi temps réel.

## 🌟 Nouveautés v2.1 - Révolution Technologique

### ⚡ Performances et Cache Intelligent
- **Cache SQLite** : Système de cache persistant avec TTL (7 jours)
- **3-5x plus rapide** : Évite les re-traductions grâce au cache intelligent  
- **Traduction par batch** : Parallélisation des requêtes API
- **Patterns pré-compilés** : Extraction optimisée avec regex compilés
- **Retry automatique** : Système de retry avec backoff exponentiel
- **Gestion d'erreurs robuste** : Fallback automatique en cas d'échec

### 🖥️ Interface Graphique Intégrée
- **GUI tkinter complète** : Interface utilisateur simple et intuitive
- **Sélection de dossiers** : Navigation graphique pour les chemins
- **Barre de progression visuelle** : Suivi temps réel des opérations
- **Logs intégrés** : Affichage des opérations en cours dans l'interface
- **Statistiques du cache** : Visualisation des performances en temps réel
- **Mode graphique ou ligne de commande** : Choix selon vos préférences

### 🧠 Analyse Intelligente Améliorée
- **Détection automatique des formats** : Analyse tous les fichiers par contenu
- **Score de confiance avancé** : Calcule la probabilité de contenu traduisible (0-100%)
- **Reconnaissance des traductions** : Détecte automatiquement les fichiers déjà traduits
- **Exclusion intelligente** : Ignore automatiquement les fichiers `.backup` et traduits
- **Validation avec suggestions** : Système de validation avec recommandations détaillées

### 📊 Suivi de Progression Nouvelle Génération
- **Statistiques temps réel** : Taux de cache, progression, estimations
- **Reprise intelligente** : Continue exactement où vous vous étiez arrêté  
- **Rapports détaillés** : Analyse complète avec suggestions d'optimisation
- **Mode parallélisé** : Traitement simultané de plusieurs fichiers

### 🛡️ Modes de Traitement Adaptatifs
- **Stratégies multiples** : Conservative, Agressive, Sûre, Test-First
- **Tests automatiques** des méthodes de réinsertion avant application
- **Traitement automatique intelligent** avec choix de la meilleure stratégie
- **Validation d'intégrité avancée** : Score de qualité avec suggestions détaillées

### 🎮 Fonctionnalités Principales Nouvelle Génération

- ⚡ **Cache SQLite intelligent** : 3-5x plus rapide, évite les re-traductions
- 🖥️ **Interface graphique intégrée** : GUI tkinter complète et intuitive  
- 🔄 **Traduction par batch parallélisée** : Système de traduction optimisé
- 🛡️ **Retry automatique robuste** : Backoff exponentiel et gestion d'erreurs
- 🧠 **Analyse intelligente IA** : Hugging Face + validation avancée
- 🎯 **Préservation parfaite des tokens** : Conservation des formats de jeu
- 📝 **Gestion contextuelle avancée** : Noms propres et termes techniques
- 📊 **Suivi temps réel** : Progression, statistiques, estimation du temps
- 📈 **Logs et rapports détaillés** : Analyse complète avec suggestions
- 🔍 **Support multi-formats intelligent** : Détection automatique par contenu
- 🚫 **Exclusion automatique** : Fichiers `.backup` et déjà traduits
- 💾 **Validation avec suggestions** : Score de qualité et recommandations

## ✨ Fonctionnalités détaillées

### 🧠 Analyse intelligente des textes
- Utilisation du modèle Hugging Face pour l'analyse de texte
- Détection précise des phrases traduisibles
- Filtrage intelligent des textes non naturels
- Adaptation contextuelle des critères de traduction

### 🎯 Traduction intelligente
- Utilisation de Google Translate comme traducteur principal
- Py-googletrans comme système de secours
- Analyse contextuelle des phrases
- Préservation des noms propres et termes techniques
- Optimisation des critères de sélection des textes

### 🛡️ Protection des données
- Préservation des tokens spéciaux du jeu
- Gestion des messages en majuscules
- Protection des codes de formatage
- Conservation de la structure des fichiers
- Analyse avancée des caractères spéciaux

### 📊 Suivi et logs
- Journalisation détaillée des opérations
- Suivi des fichiers déjà traités
- Statistiques de traduction
- Rapports d'erreurs détaillés
- Logs d'analyse du modèle Hugging Face

## 🚀 Installation

### Prérequis
- Python 3.8 ou supérieur
- Git (optionnel)
- Connexion Internet stable
- 2GB d'espace disque (pour les modèles IA)

### Installation rapide

```bash
# Cloner le dépôt
git clone https://github.com/votre-username/Persona3FES-FRPatch.git
cd Persona3FES-FRPatch

# Installer les dépendances
pip install -r requirements.txt

# Télécharger les modèles Hugging Face (automatique au premier lancement)
python p3fes_translator.py --download-models
```

## ⚙️ Configuration

### Variables d'environnement
Créez un fichier `.env` à la racine du projet :

```env
# Configuration des traducteurs
GOOGLE_TRANSLATE_API_KEY=votre_clé_api
BACKUP_TRANSLATOR_TIMEOUT=30

# Configuration des logs
LOG_LEVEL=INFO
LOG_FILE=translation.log

# Configuration du modèle Hugging Face
HUGGINGFACE_MODEL=facebook/roberta-hate-speech-dynabench-r4-target
MODEL_CONFIDENCE_THRESHOLD=0.3
```

### Préparation des fichiers
1. Créez le dossier `GameFiles/`
2. Placez-y les fichiers à traduire
3. Formats supportés : `.pm1`, `.pac`, `.pak`, `.bf`, `.tbl`

## 💻 Utilisation

### 🖥️ Interface Graphique (Nouveau!)
```bash
python p3fes_translator.py --gui
```
**Interface utilisateur complète avec boutons, barres de progression et logs visuels.**

### 🚀 Traduction Automatique Optimisée
```bash
# Mode automatique avec cache et parallélisation
python p3fes_translator.py --auto-test

# Analyse intelligente (recommandé en premier)
python p3fes_translator.py --analyze

# Voir les fichiers restants uniquement
python p3fes_translator.py --remaining

# Suivi du progrès avec statistiques
python p3fes_translator.py --progress
```

### 💾 Gestion du Cache Intelligent
```bash
# Statistiques du cache
python p3fes_translator.py --cache-stats

# Nettoyer le cache expiré
python p3fes_translator.py --clean-cache
```

### 🔧 Options Classiques
```bash
# Mode verbose avec nouvelles fonctionnalités
python p3fes_translator.py --verbose --auto-test

# Traduction d'un fichier spécifique
python p3fes_translator.py --file chemin/vers/fichier.pm1

# Mode test (analyse sans modification)
python p3fes_translator.py --test
```

## 📊 Modes d'analyse

### 🔍 Analyse Intelligente
```bash
# Analyser tous les fichiers (détecte les traductions existantes)
python p3fes_translator.py --analyze

# Voir seulement les fichiers restants à traduire
python p3fes_translator.py --remaining

# Afficher le progrès détaillé avec statistiques
python p3fes_translator.py --progress
```

### 🤖 Traitement Automatique
```bash
# Mode automatique standard (ignore les fichiers traduits)
python p3fes_translator.py --auto

# Mode automatique avec tests de réinsertion
python p3fes_translator.py --auto-test

# Contrôler la sensibilité (score de confiance minimum)
python p3fes_translator.py --auto --min-score 0.8
```

### 📈 Workflow Recommandé
```bash
# 1. Première analyse pour voir l'état
python p3fes_translator.py --analyze

# 2. Voir exactement ce qui reste à faire
python p3fes_translator.py --remaining

# 3. Traduction automatique sécurisée
python p3fes_translator.py --auto-test

# 4. Vérifier le progrès
python p3fes_translator.py --progress

# 5. Répéter 3-4 jusqu'à 100%
```

### 🎯 Fonctionnalités Avancées
- **Détection automatique des traductions** : Ignore les fichiers déjà traduits
- **Exclusion des fichiers .backup** : Évite les doublons et fichiers temporaires
- **Stratégies adaptatives** : Choisit automatiquement la meilleure méthode de réinsertion
- **Reprise intelligente** : Continue exactement où la traduction s'était arrêtée
- **Estimation du temps** : Calcule le temps restant basé sur l'analyse

## 📁 Structure du projet

```
Persona3FES-FRPatch/
├── 📂 GameFiles/           # Fichiers source du jeu
├── 📂 TranslatedFiles/     # Fichiers traduits et données
│   ├── 📂 extracted/      # Textes extraits (JSON)
│   ├── 📂 translated/     # Textes traduits (JSON)  
│   ├── 📂 reinjected/     # Fichiers réinjectés
│   ├── 📂 analysis/       # 🆕 Rapports d'analyse intelligent
│   │   ├── file_analysis_report.json          # Analyse des fichiers
│   │   └── reinsertion_test_results.json      # Résultats des tests
│   └── 📂 cache/          # 🆕 Cache SQLite intelligent
│       └── translation_cache.db               # Base de données cache
├── 📄 p3fes_translator.py  # 🆕 Script principal v2.1 avec GUI
├── 📄 test_installation.py # Tests de base
├── 📄 test_reinsert.py     # Tests de réimplémentation
├── 📄 requirements.txt     # Dépendances (mises à jour)
├── 📄 DÉMARRAGE_RAPIDE.md  # 🆕 Guide utilisateur complet v2.1
├── 📄 UTILISATION.md       # 🆕 Guide d'utilisation v2.1
└── 📄 .env                # Configuration
```

### 🆕 Nouveaux fichiers et fonctionnalités v2.1
- **`cache/`** : Cache SQLite intelligent pour accélérer les traductions (3-5x plus rapide)
- **Interface graphique intégrée** : GUI tkinter complète dans le script principal
- **`analysis/`** : Rapports détaillés d'analyse avec suggestions d'amélioration
- **`test_reinsert.py`** : Tests avancés des méthodes de réinsertion adaptatives
- **`DÉMARRAGE_RAPIDE.md`** : Guide complet v2.1 avec toutes les nouvelles fonctionnalités
- **`UTILISATION.md`** : Guide d'utilisation mis à jour avec workflow optimisé
- **Traduction par batch** : Parallélisation automatique des requêtes API
- **Retry intelligent** : Système de retry avec backoff exponentiel intégré
- **Validation avancée** : Score de qualité avec suggestions détaillées

## 🔧 Dépannage

### Problèmes courants

| Problème | Solution |
|----------|----------|
| Erreur de traduction | Vérifier la connexion Internet et les logs |
| Fichiers non trouvés | Vérifier les permissions et le chemin |
| Erreur d'encodage | Vérifier le format des fichiers source |
| Erreur modèle IA | Vérifier l'espace disque et la connexion Internet |
| Textes non traduits | Vérifier les logs d'analyse du modèle |

### Logs et débogage
- Consultez `translation.log` pour les détails
- Utilisez le mode verbose pour plus d'informations
- Vérifiez les permissions des dossiers
- Analysez les logs du modèle Hugging Face

## 🤝 Contribution

Les contributions sont les bienvenues ! Assurez-vous d'avoir une copie légale de **Shin Megami Tensei: Persona 3 FES (USA)** puis :

1. Fork le projet
2. Créez une branche (`git checkout -b feature/Amelioration`)
3. Committez vos changements (`git commit -m 'Ajout d'une fonctionnalité'`)
4. Push vers la branche (`git push origin feature/Amelioration`)
5. Ouvrez une Pull Request

### Points d'amélioration recherchés
- 🎯 Amélioration de la qualité des traductions
- 🧠 Optimisation du modèle d'analyse de texte
- 🔧 Support de nouveaux formats de fichiers
- 📝 Documentation plus détaillée
- 🐛 Correction de bugs
- 🤖 Intégration d'autres modèles d'IA

## 📝 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

<div align="center">

### 📫 Contact

[![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Inkflow59)

*Fait avec ❤️ par et pour la communauté Persona française*

</div>