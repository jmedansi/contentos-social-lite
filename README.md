# ContentOS Social Lite (Banc d'Essai Réseaux Sociaux)

Version allégée de **ContentOS**, conçue exclusivement pour les testeurs de réseaux sociaux (Meta/Instagram, LinkedIn, X, TikTok) et les audits d'applications (ex: *Meta App Review*).

---

## 🎯 Périmètre Fonctionnel

- ✅ **Publication Directe :** Envoi immédiat sur Facebook, Instagram et LinkedIn (texte + médias).
- ✅ **Inbox Sociale :** Visualisation des commentaires et messages privés reçus.
- ✅ **Réponses Manuelles :** Répondre directement aux commentaires et DM sans quitter l'interface.
- ✅ **Webhooks Opérationnels :** Endpoints `/webhooks/meta` (validation par challenge + réception des événements de messagerie et de commentaires en temps réel).
- ❌ **AUCUNE IA :** Zéro appel API (Groq, OpenAI, Claude, etc.), zéro coût LLM, aucune fuite de clés.
- ❌ **AUCUNE PLANIFICATION :** Aucun daemon de cron ou de background task requis.

---

## 🚀 Déploiement sur Vercel (en 2 minutes)

### 1. Pré-requis
1. Créer une base de données PostgreSQL gratuite sur [Neon.tech](https://neon.tech) ou [Supabase](https://supabase.com).
2. Copier la chaîne de connexion `postgresql://...`.

### 2. Variables d'environnement sur Vercel
Ajoutez les variables suivantes dans **Project Settings > Environment Variables** :
- `DATABASE_URL` : Votre URL de connexion Postgres (ex: Neon ou Supabase).
- `APP_URL` : L'URL de votre déploiement Vercel (ex: `https://votre-projet.vercel.app`).
- `META_VERIFY_TOKEN` : `contentos_secret_token_123` (ou votre propre token secret).
- `META_CLIENT_ID` : Votre App ID Meta.
- `META_CLIENT_SECRET` : Votre App Secret Meta.
- `LINKEDIN_CLIENT_ID` : (Optionnel) Client ID LinkedIn.
- `LINKEDIN_CLIENT_SECRET` : (Optionnel) Client Secret LinkedIn.

### 3. Déploiement GitHub
1. Pousser ce dépôt sur GitHub (`git push origin main`).
2. Importer le dépôt sur Vercel : Vercel détecte automatiquement le fichier [`vercel.json`](file:///d:/ContentOS-Social-Lite/vercel.json) et la fonction Python [`api/index.py`](file:///d:/ContentOS-Social-Lite/api/index.py).

---

## 🔗 Configuration des Webhooks Meta
Dans votre compte [Meta for Developers](https://developers.facebook.com/) :
1. Allez dans **Webhooks** (sélectionnez `Page` ou `Instagram`).
2. Renseignez l'URL de rappel : `https://votre-projet.vercel.app/webhooks/meta`
3. Renseignez le Token de vérification : `contentos_secret_token_123` (ou celui défini dans `META_VERIFY_TOKEN`).
4. Abonnez-vous aux champs : `feed`, `messages`, `messaging_postbacks`, `comments`.
