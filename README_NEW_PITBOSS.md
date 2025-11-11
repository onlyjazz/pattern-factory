# 🚀 New LLM-Supervised Pitboss with gpt-4o-mini

## Quick Start

The new pitboss system uses gpt-4o-mini with function calling to orchestrate tool execution. The LLM itself decides which tools to call and in what order, making the system more flexible and adaptive.

### ✅ Environment is Already Configured!

Your `.env` file has been updated with:
```env
PITBOSS_STRATEGY=llm_supervised
GPT5_MINI_AVAILABLE=true
PREFER_FLEXIBILITY=true
```

## 🎯 How to Use

### 1. Check Configuration
```bash
python run_new_pitboss.py --check
```

### 2. Run Interactive Mode
```bash
python run_new_pitboss.py
```

In interactive mode, you can:
- Type `rule ALT > 120` to execute a rule
- Type `demo` to run a demonstration
- Type `status` to see configuration
- Type `help` for all commands
- Type `exit` to quit

### 3. Run a Demo
```bash
python run_new_pitboss.py --demo
```

### 4. Execute a Single Rule
```bash
python run_new_pitboss.py --rule "Flag subjects with ALT > 3x ULN"
```

### 5. Process a DSL File
```bash
python run_new_pitboss.py --dsl clovis.yaml
```

## 🏗️ Architecture

### Traditional vs LLM-Supervised

| Aspect | Traditional (Old) | LLM-Supervised (New) |
|--------|------------------|---------------------|
| **Orchestration** | Python code | GPT-5-mini |
| **Flexibility** | Fixed sequence | Adaptive |
| **API Calls** | Multiple | Single with function calling |
| **Error Handling** | Explicit | Natural recovery |
| **Model** | GPT-4o (SQL only) | gpt-4o-mini (everything) |

### How It Works

1. **User provides rule** → 
2. **System sends to gpt-4o-mini with tool definitions** →
3. **gpt-4o-mini responds with function calls**:
   - `sql_pitboss`: Generate SQL
   - `data_table`: Create materialized table
   - `register_rule`: Register in registry
   - `insert_alerts`: Log execution
4. **Python executes requested tools** →
5. **Results returned to user**

### Context Injection Pattern

The system uses strategic context ordering to influence the LLM:

```
PROTOCOL (low weight) → DATA (medium) → RULES (high weight)
                                              ↑
                                    Maximum influence
```

This leverages how LLMs process tokens, with recent tokens having more influence on generation.

## 🔧 Configuration Options

### Switch Between Strategies

Edit `.env` file:

```env
# For traditional Python orchestration
PITBOSS_STRATEGY=traditional
GPT5_MINI_AVAILABLE=false

# For LLM-supervised orchestration
PITBOSS_STRATEGY=llm_supervised
GPT5_MINI_AVAILABLE=true

# For hybrid (auto-select based on complexity)
PITBOSS_STRATEGY=hybrid
GPT5_MINI_AVAILABLE=true

# For automatic detection
PITBOSS_STRATEGY=auto
```

### Advanced Configuration

Create a `pitboss_config.json`:

```json
{
  "supervisor": {
    "strategy": "llm_supervised",
    "prefer_flexibility": true,
    "complex_rule_indicators": ["join", "aggregate", "multiple"]
  },
  "models": {
    "orchestration_model": "gpt-5-mini",
    "temperatures": {
      "gpt-5-mini_orchestration": 0.25
    }
  }
}
```

## 📊 Example Output

```
🎯 Running Single Rule: ALT > 120

[LLM Supervisor] Calling sql_pitboss with {'protocol_id': 'USER-001', 'rule_code': 'USER_RULE', 'sql': 'SELECT USUBJID, ALT FROM adlb_clovis WHERE ALT > 120'}
[LLM Supervisor] Calling data_table with {'protocol_id': 'USER-001', 'rule_code': 'USER_RULE', 'table_name': 'res_user_001_user_rule'}
[LLM Supervisor] Calling register_rule with {'protocol_id': 'USER-001', 'rule_code': 'USER_RULE'}
[LLM Supervisor] Calling insert_alerts with {'protocol_id': 'USER-001', 'rule_code': 'USER_RULE', 'status': 'executed'}

✅ Rule executed successfully!
  - sql_pitboss: success
  - data_table: success (5 rows)
  - register_rule: success
  - insert_alerts: success
```

## 🔄 Comparison Script

To see the difference between approaches:

```bash
python services/compare_approaches.py
```

## 📚 Key Files

- `run_new_pitboss.py` - Easy-to-use interface for the new system
- `services/pitboss_llm_supervisor.py` - GPT-5-mini orchestrated implementation
- `services/pitboss_supervisor.py` - Traditional Python orchestration
- `services/config_advanced.py` - Configuration management
- `services/compare_approaches.py` - Architecture comparison

## 🎯 Benefits of LLM Supervision

1. **Adaptive Execution**: LLM can skip steps if rule is invalid
2. **Natural Error Recovery**: LLM understands context and can adapt
3. **Single API Call**: More efficient for complex workflows
4. **Future-Proof**: Easy to add new tools without changing orchestration logic
5. **Context-Aware**: LLM understands the relationship between tools

## 🚦 Status Indicators

When running commands, you'll see:
- ✅ Success
- ❌ Error
- ⚠️ Warning
- ℹ️ Information
- 🎯 Processing
- 📊 Results

## 🐛 Troubleshooting

### If GPT-5-mini is not available:
```bash
# Check if it's enabled
echo $GPT5_MINI_AVAILABLE

# If not, update .env:
echo "GPT5_MINI_AVAILABLE=true" >> .env
```

### To revert to traditional approach:
```bash
# Edit .env
PITBOSS_STRATEGY=traditional
GPT5_MINI_AVAILABLE=false
```

### To see what strategy is active:
```bash
python run_new_pitboss.py --check
```

## 💡 Pro Tips

1. **Use `--demo` first** to see how the system works
2. **Start with simple rules** in interactive mode
3. **Check execution logs** to understand tool calling sequence
4. **Use hybrid mode** for production to balance cost and flexibility
5. **Monitor token usage** - shown after each execution

## 🎉 You're Ready!

Your system is configured and ready to use GPT-5-mini as the orchestrator. Try:

```bash
python run_new_pitboss.py --demo
```

Enjoy the power of LLM-supervised orchestration!