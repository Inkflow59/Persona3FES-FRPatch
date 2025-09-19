# 🚀 GUIDE D'UTILISATION RAPIDE

## Installation

1. **Installer Python 3.8+** si ce n'est pas fait
2. **Installer les dépendances**:
   ```bash
   pip install -r requirements.txt
   ```

## Préparation

1. **Créer le dossier GameFiles** (déjà fait)
2. **Copier vos fichiers** de Persona 3 FES dans `GameFiles/`
3. **Faire une sauvegarde** de vos fichiers originaux !

## Utilisation

### Mode test (recommandé en premier)
```bash
python p3fes_translator.py --test
```
Affiche les textes qui seraient traduits sans les modifier.

### Traduction complète
```bash
python p3fes_translator.py
```
Traduit tous les fichiers dans GameFiles/.

### Traduction d'un fichier spécifique
```bash
python p3fes_translator.py --file GameFiles/MSG_001.pm1
```

### Mode verbose (pour débogage)
```bash
python p3fes_translator.py --verbose
```

## Résultats

- **Fichiers traduits**: Les originaux sont modifiés directement
- **Logs**: `translation.log` contient tous les détails
- **Sauvegardes**: Dossier `TranslatedFiles/` contient les extractions et versions de travail

## Dépannage

| Problème | Solution |
|----------|----------|
| "Aucun fichier trouvé" | Vérifiez que vos fichiers sont dans GameFiles/ |
| "Erreur d'extraction" | Vérifiez que les fichiers ne sont pas corrompus |
| "Erreur de traduction" | Vérifiez votre connexion Internet |
| "Permission denied" | Lancez en tant qu'administrateur |

## 📁 Structure créée

```
Persona3FES-FRPatch/
├── GameFiles/          ← VOS FICHIERS ICI
├── TranslatedFiles/    ← Fichiers de travail (auto-créé)
│   ├── extracted/     ← Textes extraits en JSON
│   ├── translated/    ← Textes traduits en JSON
│   └── reinjected/    ← Versions modifiées avant réinjection
├── p3fes_translator.py ← Script principal
└── translation.log    ← Journal détaillé (auto-créé)
```