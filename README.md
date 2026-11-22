# Stanley Black & Decker Innovation Assessment

Independent Streamlit app (not TechLife SSO). Assessment, Word, and Excel match Innovation Analysis.

## Login

- Apply with email → admin approves.
- Initial password: `1234567`. Users change it after login.
- Same browser stays signed in about 30 days.
- Top right: 中文 / English / ⚙️ admin (`Laurence_ku`).

## Setup

1. In the existing TechLife Supabase SQL editor, run `sql/sbd_schema.sql`. If tables already exist, also run `sql/sbd_migration_logo.sql` so admin can save a company logo.
2. Create a GitHub repo, push this folder, deploy on Streamlit Cloud with `app.py`.
3. Paste `secrets.example.toml` values into Streamlit Cloud secrets (use the **service role** key).
4. Open ⚙️, sign in as admin, set admin emails, approve requests or add users.

TechLife portal is unchanged.
