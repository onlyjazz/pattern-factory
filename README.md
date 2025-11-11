# Pattern Factory

Rev 2.0 
Key Achievements in This Release:

1.  Uses the LLM as the supervisor 
2. Uses PROTOCOL, DATA and RULES for few-shot learning     
3. Natural Language Revolution: Users can now interact with the system using plain English - no more memorizing commands!
4. Architectural Simplification: Removed complex configuration and strategy patterns, resulting in a cleaner, more maintainable codebase.
5. Enhanced User Experience: Beautiful HTML formatting for AI responses, making information easier to read and understand.
6. Improved Reliability: Fixed all the duplicate message issues and improved error handling throughout the system.
7. Security: Added XSS protection to ensure safe rendering of user content.

This is a significant milestone that transforms the Clinical Trial Data Review System from a command-based tool to an intelligent, conversational assistant that understands natural language and provides rich, formatted responses. The system is now more accessible to non-technical users while maintaining all the power needed for complex data analysis tasks.

The release is now live and ready for production use! 🚀

To install - git pull cycle7

Update the environment
```
pip install -r requirements.txt
npm install
```

Pull the latest DSL program, you'll be loading it in the frontend app
```
cd <your dsl directory>
git pull
```

Run the API Server:
```
python -m services.run
```

Run the Frontend - load clovis-dsl-v20-test-cases.yaml
```
npm run dev
```

## Installation from scratch

1. Set up pyenv:

```
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
```

2. Install the required Python version using pyenv:
```
pyenv install 3.13.3
pyenv global 3.13.3
```

3. Double check that Python has been properly installed:
```
source ~/.zshrc
pyenv --version
```

4. Install the required Python packages:
```
Build Python environment from the imports 
1. pip install pip-tools 
2. cd services/ 
3. pip-compile requirements.in 
4. pip-sync requirements.txt

```

5. Pull the database, code and DSL repository
```
Install the database, DSL repository and code under ~/code
cd ~/code
brew install git
brew install git-lfs

# Pull the database
git clone git@github.com:onlyjazz/data-review-database.git


# Pull the DSL repository
git clone https://github.com/clinical-trial-data-review/data-review-dsl.git

# Pull the code
git clone git@github.com:onlyjazz/clinical-trial-data-review.git
# Checkout the cycle6 branch
git pull origin cycle6
git checkout cycle6
```

6. Setup your Environment file - .env

```    
# Database configuration
DATABASE_URL=duckdb://~/code/data-review-database/datareview
DATABASE_LOCATION=~/code/data-review-database/datareview

# API settings
API_HOST=0.0.0.0
API_PORT=8000

#OpenAI
OPENAI_API_KEY=<put your OpenAI API key here>

# Database Configuration
DB_TYPE=duckdb

# Snowflake Configuration (for future use)
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=CLINICAL_TRIALS
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=SYSADMIN
```

7. Install the required Node packages:
```
nvm install node
nvm use node
nvm alias default node
npm install -g npm
```

8. Run the API Server:
```
python -m services.run
```

9. Set up SvelteKit and install dependencies
```
npx create-svelte@latest my-app
cd my-app
npm install
```

10. Run the front end
```
npm run dev
```

Dev mode Debugging tips
```
Run the API server first. It locks the db. You cannot run 2 instances.

If the  API returns 500 it's probably related to the db - 
double-check that and 
git pull data-review-database


Check locations in your .env file

Make sure you  defined the OPENAI_API_KEY in .env
```