import re
import os
import sys
import asyncio
import logging
from typing import List, Optional
from difflib import get_close_matches
import uuid
import pdfplumber
from dotenv import load_dotenv
import openai
from .api import read_ddt_items, add_rule, Rule, conn

# --- Load env and OpenAI key ---
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Synonym map (extend as needed) ---
SYNONYM_MAP = {
    "ctcae grade": "CTCAE_GRADE",
    "toxicity grade": "CTCAE_GRADE",
    "serious adverse event": "SAE",
    "fatal": "CTCAE_GRADE",
    "life-threatening": "CTCAE_GRADE",
    "severe": "CTCAE_GRADE"
}

# --- GPT wrapper ---
class LanguageAgent:
    async def process_rule(self, rule_text: str, prompt: Optional[str] = None) -> str:
        system_prompt = prompt or (
            "You are an expert clinical trial AI. Convert natural language adverse event descriptions "
            "into logic rules like 'CTCAE_GRADE >= 3', 'SAE = TRUE'. Only return the rule itself, nothing else."
        )
        try:
            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": rule_text}
                ],
                temperature=0.2,
                max_tokens=100,
                top_p=1.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI rule processing failed: {e}")
            return f"[ERROR] {rule_text}"

# --- Build fuzzy variable map ---
def build_variable_map() -> dict:
    items = read_ddt_items()
    variable_map = {}
    for item in items:
        desc = item.description.strip().lower()
        var = item.item_id.strip().upper()
        variable_map[desc] = var
        variable_map[var.lower()] = var
        for token in re.findall(r'\w+', desc):
            if token not in variable_map:
                variable_map[token] = var
    return variable_map

# --- Map GPT terms to variable names ---
def map_variables(dsl: str, variable_map: dict) -> str:
    original = dsl
    mapped = dsl

    for phrase, var in SYNONYM_MAP.items():
        mapped = re.sub(rf"\b{re.escape(phrase)}\b", var, mapped, flags=re.IGNORECASE)

    for desc, var in variable_map.items():
        if re.search(rf"\b{re.escape(desc)}\b", mapped, flags=re.IGNORECASE):
            mapped = re.sub(rf"\b{re.escape(desc)}\b", var, mapped, flags=re.IGNORECASE)

    words = set(re.findall(r'\b\w+\b', original.lower()))
    for word in words:
        match = get_close_matches(word, variable_map.keys(), n=1, cutoff=0.85)
        if match:
            mapped = re.sub(rf"\b{re.escape(word)}\b", variable_map[match[0]], mapped, flags=re.IGNORECASE)

    return mapped

# --- AE parser class ---
class AdverseEventParser:
    def __init__(self):
        self.agent = LanguageAgent()
        self.variable_map = build_variable_map()

    def extract_text_from_pdf(self, path: str) -> str:
        logger.info(f"Reading PDF: {path}")
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

    def extract_ae_blocks(self, text: str) -> List[str]:
        # Extract section 9 or Appendix E text
        match = re.search(r"(?s)9\. SAFETY DATA COLLECTION, RECORDING, AND REPORTING(.*?)(10\. STATISTICAL CONSIDERATIONS|Appendix)", text)
        if not match:
            match = re.search(r"(?s)Appendix E\. Adverse Event Assessments(.*?)(Appendix F|End of Document)", text)

        block = match.group(1).strip() if match else ""
        return [line.strip("-•\n ").strip() for line in block.split("\n") if len(line.strip()) > 10]

    async def parse_pdf(self, pdf_path: str) -> List[str]:
        raw_text = self.extract_text_from_pdf(pdf_path)
        ae_criteria = self.extract_ae_blocks(raw_text)
        final_rules = []

        for rule in ae_criteria:
            raw_dsl = await self.agent.process_rule(
                rule,
                prompt="You are an expert clinical trial AI. Convert natural language adverse event descriptions into logic rules like 'CTCAE_GRADE >= 3', 'SAE = TRUE'. Only return the rule itself, nothing else."
            )
            mapped_dsl = map_variables(raw_dsl, self.variable_map)
            final_rules.append(f"if {mapped_dsl} then flag")

        return final_rules

# --- Main runner ---
if __name__ == "__main__":
    from pathlib import Path

    pdf_path = "./protocols/20050203.pdf"
    protocol_id = Path(pdf_path).stem

    try:
        result = conn.execute(
            "SELECT sponsor, date_created, date_amended FROM protocols WHERE protocol_id = ?",
            (protocol_id,)
        ).fetchone()

        if result is None:
            raise ValueError(f"Protocol ID {protocol_id} not found in database.")

        sponsor, date_created, date_amended = result

    except Exception as e:
        print(f"❌ Failed to fetch protocol metadata: {e}")
        sys.exit(1)

    parser = AdverseEventParser()
    loop = asyncio.get_event_loop()
    rules = loop.run_until_complete(parser.parse_pdf(pdf_path))

    print("\n--- Parsed Adverse Event DSL Rules ---\n")
    for rule_code in rules:
        print("DSL:", rule_code)

        rule = Rule(
            rule_id=str(uuid.uuid4()),
            protocol_id=protocol_id,
            sponsor=sponsor,
            rule_code=rule_code,
            date_created=date_created,
            date_amended=date_amended
        )

        try:
            add_rule(rule)
            print("✔ Inserted via add_rule():", rule.rule_code)
        except Exception as e:
            print("❌ add_rule() failed:", rule.rule_code)
            print("   Error:", e)
