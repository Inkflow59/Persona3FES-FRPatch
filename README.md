# 🎮 Persona 3 FES - Patch de Traduction Française

<div align="center">

![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)
![Licence](https://img.shields.io/badge/licence-MIT-yellow.svg)
![Statut](https://img.shields.io/badge/statut-en%20développement-orange.svg)
![IA](https://img.shields.io/badge/IA-Hugging%20Face-purple.svg)

[English](README.md) | [Français](README.fr.md)

*Traduction automatique des fichiers de texte de Persona 3 FES de l'anglais vers le français*

<img src="https://raw.githubusercontent.com/your-username/Persona3FES-FRPatch/main/assets/banner.png" alt="Banner" width="600"/>

</div>

## 📋 Table des matières

- [À propos](#-à-propos)
- [✨ Fonctionnalités](#-fonctionnalités)
- [🚀 Installation](#-installation)
- [⚙️ Configuration](#️-configuration)
- [💻 Utilisation](#-utilisation)
- [📁 Structure du projet](#-structure-du-projet)
- [🔧 Dépannage](#-dépannage)
- [🤝 Contribution](#-contribution)
- [📝 Licence](#-licence)

## 🎯 À propos

Ce projet vise à automatiser la traduction des fichiers de texte du jeu Persona 3 FES de l'anglais vers le français. Il utilise des algorithmes avancés et l'intelligence artificielle pour préserver les tokens spéciaux du jeu tout en assurant une traduction de qualité optimale.

### 🎮 Fonctionnalités principales

- 🔄 Traduction automatique avec double système de secours
- 🧠 Analyse intelligente des textes avec Hugging Face
- 🛡️ Préservation intelligente des tokens spéciaux
- 📝 Gestion contextuelle des noms propres
- 📊 Suivi des fichiers traités
- 📈 Logs détaillés des opérations
- 🎯 Support multi-formats

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

### Lancer la traduction
```bash
python p3fes_translator.py
```

### Options avancées
```bash
# Mode verbose
python p3fes_translator.py --verbose

# Traduction d'un fichier spécifique
python p3fes_translator.py --file chemin/vers/fichier.pm1

# Mode test
python p3fes_translator.py --test
```

## 📁 Structure du projet

```
Persona3FES-FRPatch/
├── 📂 GameFiles/           # Fichiers source du jeu
├── 📂 TranslatedFiles/     # Fichiers traduits
│   ├── 📂 extracted/      # Textes extraits (JSON)
│   ├── 📂 translated/     # Textes traduits (JSON)
│   └── 📂 reinjected/     # Fichiers réinjectés
├── 📄 p3fes_translator.py  # Script principal
├── 📄 requirements.txt     # Dépendances
└── 📄 .env                # Configuration
```

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