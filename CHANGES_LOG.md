# Journal des Modifications - Parcelles (13/11/2025)

## 🎯 Objectif
Modifier le modèle `Parcelle` pour rendre **seules obligatoires** `titre_foncier` et `plan_cadastral`, et remplacer les coordonnées texte par un **fichier GeoJSON**.

---

## ✅ Modifications Effectuées

### 1️⃣ **Modèle `Parcelle` (`parcelles/models.py`)**

#### Changements :
- ❌ **Suppression** du champ `coordonnees` (TextField)
- ✅ **Ajout** du champ `fichier_geojson` (FileField, optionnel)
- 🔴 `titre_foncier` : **OBLIGATOIRE** (blank=False, null=False)
- 🔴 `plan_cadastral` : **OBLIGATOIRE** (blank=False, null=False)
- 🟢 `certificat_propriete` : **OPTIONNEL** (blank=True, null=True)
- 🟢 `acte_mutation` : **OPTIONNEL** (blank=True, null=True)
- 🟢 `certificat_hypotheque` : **OPTIONNEL** (inchangé)

#### Détails techniques :
```python
# AVANT
titre_foncier = ForeignKey(TitreFoncier, on_delete=SET_NULL, blank=True, null=True)
plan_cadastral = ForeignKey(PlanCadastral, on_delete=SET_NULL, blank=True, null=True)
certificat_propriete = FileField(upload_to="certif_propriete/")  # Obligatoire
acte_mutation = FileField(upload_to="acte_mutation/")  # Obligatoire
coordonnees = TextField()  # Texte GeoJSON

# APRÈS
titre_foncier = ForeignKey(TitreFoncier, on_delete=PROTECT, blank=False, null=False)
plan_cadastral = ForeignKey(PlanCadastral, on_delete=PROTECT, blank=False, null=False)
certificat_propriete = FileField(upload_to="certif_propriete/", blank=True, null=True)  # Optionnel
acte_mutation = FileField(upload_to="acte_mutation/", blank=True, null=True)  # Optionnel
fichier_geojson = FileField(upload_to="geojson/", blank=True, null=True)  # Fichier GeoJSON
```

---

### 2️⃣ **Serializer `ParcelleSerializer` (`parcelles/serializers.py`)**

#### Changements :
- ❌ Suppression du champ `coordonnees`
- ✅ Ajout du champ `fichier_geojson` (optionnel)
- 🔴 `titre_foncier` : **required=True**
- 🔴 `plan_cadastral` : **required=True**
- 🟢 `certificat_propriete` : **required=False**
- 🟢 `acte_mutation` : **required=False**

#### Validation `create()` :
- Vérifie que `titre_foncier` et `plan_cadastral` sont fournis
- Crée les documents obligatoires dans la DB
- Ignore les fichiers optionnels manquants

---

### 3️⃣ **Vue `ParcelleViewSet` (`parcelles/views.py`)**

#### Changements dans `perform_update()` :
- ✅ Ajout du traitement du `fichier_geojson`
- ✅ Les fichiers optionnels ne sont mis à jour que s'ils sont fournis
- Les fichiers obligatoires peuvent être mis à jour individuellement

---

### 4️⃣ **Vue `TransactionViewSet` (`transactions/views.py`)**

#### Changements dans `download_documents()` :
- ✅ Ajout du téléchargement du `fichier_geojson` dans le ZIP
- Tous les fichiers sont inclus dans le sous-dossier `Parcelle/`

---

### 5️⃣ **Migration Django**

#### Fichier créé :
`parcelles/migrations/0004_remove_parcelle_coordonnees_parcelle_fichier_geojson_and_more.py`

#### Opérations :
1. Suppression du champ `coordonnees`
2. Ajout du champ `fichier_geojson`
3. Modification de `certificat_propriete` (optionnel)
4. Modification de `acte_mutation` (optionnel)
5. Modification de `titre_foncier` (on_delete=PROTECT)
6. Modification de `plan_cadastral` (on_delete=PROTECT)

✅ **Statut** : Appliquée avec succès

---

## 📊 Tableau Récapitulatif

| Champ | Avant | Après | Type |
|-------|-------|-------|------|
| `titre_foncier` | Optionnel | **Obligatoire** | ForeignKey |
| `plan_cadastral` | Optionnel | **Obligatoire** | ForeignKey |
| `certificat_propriete` | Obligatoire | **Optionnel** | FileField |
| `acte_mutation` | Obligatoire | **Optionnel** | FileField |
| `certificat_hypotheque` | Optionnel | **Optionnel** | ForeignKey |
| `coordonnees` | Texte | **SUPPRIMÉ** | - |
| `fichier_geojson` | - | **AJOUTÉ** | FileField |

---

## 🔍 Dépendances Mises à Jour

### ✅ Fichiers modifiés :
1. `parcelles/models.py`
2. `parcelles/serializers.py`
3. `parcelles/views.py`
4. `transactions/views.py` (download_documents)

### ✅ Migrations appliquées :
1. `parcelles/migrations/0004_*`

### ✅ Validation :
- ✓ Pas d'erreurs Django (`manage.py check`)
- ✓ Migrations appliquées avec succès
- ✓ Tous les fichiers dépendants mis à jour

---

## 🚀 Points Importants

### À noter :
- Les parcelles **existantes** doivent avoir `titre_foncier` et `plan_cadastral` remplis
- Le fichier GeoJSON est **optionnel** et peut être fourni ultérieurement
- Les certificats et actes peuvent désormais être omis lors de la création
- La structure de téléchargement des documents reste cohérente

### En cas de problème :
- Vérifier que les parcelles existantes ont bien `titre_foncier` et `plan_cadastral`
- Sinon, créer les documents manquants via Django admin ou une migration RunPython

---

## 📝 Exemple d'utilisation API

### Création d'une parcelle (obligatoire) :
```json
{
  "titre": "Parcelle ABC",
  "taille_m2": 1000,
  "prix_m2": 50,
  "localisation": "Yaoundé",
  "titre_foncier": "<file>",
  "plan_cadastral": "<file>"
}
```

### Mise à jour avec GeoJSON (optionnel) :
```json
{
  "fichier_geojson": "<file>",
  "certificat_propriete": "<file>"
}
```

---

✅ **Statut** : Toutes les modifications ont été appliquées avec succès le 13/11/2025 à 18:30
