# Cline free models on CANFAR

1. Install: `astroai-lab agent install cline`
2. OpenRouter key (free tier): https://openrouter.ai/keys
3. Configure:
   ```bash
   export OPENROUTER_API_KEY=sk-or-v1-...
   astroai-lab agent models free --preset coding
   ```
   Or manually:
   ```bash
   cline auth -p openrouter -k "$OPENROUTER_API_KEY" -m qwen/qwen3-coder:free
   ```
4. Long context: `--preset long` → `google/gemini-2.0-flash-lite:free`
5. Use agentic compaction for long sessions: `cline --compaction agentic "task"`

Cline provider promos (no OpenRouter key) may appear — run `cline auth` and pick the Cline provider when offered.
