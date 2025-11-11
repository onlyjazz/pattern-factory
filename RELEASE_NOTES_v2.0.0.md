# Release Notes - v2.0.0
## Clinical Trial Data Review System - Major Release

**Release Date**: Sep 21, 2025

---

## 🎯 Overview

Version 2.0.0 represents a major architectural overhaul of the Clinical Trial Data Review System, introducing natural language processing capabilities, simplified configuration, and enhanced user experience through intelligent AI-powered interactions.

---

## 🚀 Major Features

### 1. Natural Language Interface
- **Complete AI-Driven Interaction**: All user input is now processed through GPT-4o for intelligent intent classification
- **Smart Command Understanding**: The system automatically determines whether to:
  - Execute specific rules
  - Run all rules in the workflow
  - Answer questions about protocols, data, or rules
  - Provide help and guidance
- **No More Command Syntax**: Users can interact naturally without memorizing command formats

### 2. Simplified Architecture
- **Single Pitboss Implementation**: Removed complex strategy patterns and configuration flags
- **Eliminated Configuration Variables**:
  - Removed `GPT5_MINI_AVAILABLE`
  - Removed `PITBOSS_STRATEGY`
  - Removed all conditional strategy switching
- **Direct LLM Integration**: Streamlined to use only the LLM-supervised Pitboss implementation

### 3. Enhanced Message Formatting
- **Markdown to HTML Conversion**: AI responses are automatically converted from markdown to rich HTML
- **Professional Formatting**: Support for:
  - Lists (ordered and unordered)
  - Bold and italic text
  - Code blocks with syntax highlighting
  - Tables
  - Headers
  - Blockquotes
- **XSS Protection**: User messages are properly escaped to prevent security vulnerabilities

### 4. Improved Reliability
- **Message Deduplication**: Implemented sophisticated deduplication to prevent duplicate WebSocket messages
- **Better Error Handling**: Single, clear error messages instead of multiple redundant notifications
- **Case-Insensitive Rule Matching**: Rule codes are handled case-insensitively for better user experience

### 5. Priority Through Ordering
The Pitboss system structures prompts the LLM using priority through ordering, ensuring that the most important information—the rules—are freshest in the model’s attention window.
PROTOCOL – Title, description, and eligibility criteria (lower weight).
DATA – Data sources and required fields (medium weight).
RULES – Review logic (highest weight), including small positive/negative examples.Because LLMs weigh recent tokens more heavily, placing RULES last ensures they strongly shape the generated output.

---

## 💡 Key Improvements

### Backend Enhancements
- Consolidated Pitboss implementation into `pitboss_llm_supervisor.py`
- Added intent classification system for natural language processing
- Implemented markdown2 for HTML conversion
- Added message deduplication with memory management
- Improved SQL generation without function calling overhead

### Frontend Enhancements
- HTML rendering support with `@html` directive
- Comprehensive CSS styling for all HTML elements
- XSS protection for user input
- Improved WebSocket connection management
- Better session and chat history handling

### Developer Experience
- Simplified codebase with fewer moving parts
- Clearer separation of concerns
- Better logging and debugging capabilities
- Reduced configuration complexity

---

## 📦 Dependencies Updates

### New Dependencies
- `markdown2==2.5.4` - Markdown to HTML conversion
- `python-multipart==0.0.20` - Multipart form data handling

### Existing Dependencies
- FastAPI for backend API
- OpenAI GPT-4o for natural language processing
- DuckDB for data analytics
- SvelteKit for frontend
- WebSockets for real-time communication

---

## 🔄 Migration Notes

### Breaking Changes
1. **Configuration Changes**:
   - Remove `GPT5_MINI_AVAILABLE` from `.env`
   - Remove `PITBOSS_STRATEGY` from `.env`
   - No longer support for legacy Pitboss implementations

2. **API Changes**:
   - All messages now go through natural language processing
   - Command parsing moved from frontend to backend
   - WebSocket message format includes HTML content

### Upgrade Steps
1. Update Python dependencies:
   ```bash
   cd services/
   pip-sync requirements.txt
   ```

2. Update environment variables:
   - Remove deprecated configuration variables
   - Ensure `OPENAI_API_KEY` is set

3. Restart services:
   ```bash
   python -m services.run
   ```

---

## 🐛 Known issues

- The AI chat repeats pitboss responses several times
- The AI chat doesn't always report errors properly

## 🐛 Bug Fixes

- Resolved malformed JSON responses from LLM
- Fixed case sensitivity issues with rule codes
- Corrected WebSocket port mismatches
- Eliminated redundant error messages
- Fixed "RUN_ALL_RULES" command recognition

---

## 📈 Performance Improvements

- Reduced LLM API calls through better prompt engineering
- Faster rule execution with streamlined SQL generation
- Improved memory management with message deduplication
- Better WebSocket connection stability

---

## 🔮 Future Roadmap

- Enhanced rule building interface
- Visual query builder
- Advanced data visualization
- Rule templates and suggestions
- Batch rule execution with progress tracking
- Export capabilities for audit trails

---

## 👥 Contributors

- Development Team: Clinical Trial Data Review Project
- AI Integration: LLM-supervised Pitboss Architecture
- Testing: Continuous integration with real-world DSL scenarios

---

## 📝 Notes

This major release represents a significant step forward in making clinical trial data review more accessible and intuitive. The natural language interface removes barriers for non-technical users while maintaining the power and flexibility needed for complex data analysis tasks.

For questions or issues, please refer to the project documentation or contact the development team.

Why the DSL Is Special
Pitboss DSL acts like fine-tuning without fine-tuning:
PROTOCOL → Defines eligibility and study context.
DATA → Bridges to the database schema.
RULES → Encode review logic.


Together, these layers provide the model with clarity, structure, and actionable pathways.

---

**Version**: 2.0.0  
**Status**: Production Ready  
**License**: Proprietary
