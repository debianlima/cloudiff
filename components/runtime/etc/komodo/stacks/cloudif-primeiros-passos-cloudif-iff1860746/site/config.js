// Runtime configuration template.
// Inject these values during deployment; never commit tenant credentials.
window.CLOUDIF_CONFIG = {
  supabaseUrl: "${SUPABASE_URL}",
  supabaseAnonKey: "${SUPABASE_ANON_KEY}"
};
