import spacy
import re

nlp = spacy.load("en_core_web_sm")

AMOUNT_RE = re.compile(r'\$[\d,]+(\.\d+)?|\b\d+[kKmMbB]\b')
NUMBER_AMOUNT_RE = re.compile(r'\b\d{4,}\b|\b\d+(?:\.\d+)?\s*(?:usd|dollars|eur|euros|inr|rupees)\b', re.IGNORECASE)

def sanitise(text: str) -> str:
    doc = nlp(text)
    result = text

    for ent in reversed(doc.ents):
        label = ent.label_
        if label in ("PERSON",):         
            replacement = "[PERSON]"
        elif label in ("ORG", "PRODUCT"): 
            replacement = "[ORG]"
        elif label in ("GPE", "LOC"):    
            replacement = "[LOCATION]"
        elif label in ("DATE", "TIME"):  
            replacement = "[DATE]"
        elif label in ("MONEY", "CARDINAL", "QUANTITY"):
            replacement = "[AMOUNT]"
        else:                            
            continue
        result = result[:ent.start_char] + replacement + result[ent.end_char:]

    result = AMOUNT_RE.sub("[AMOUNT]", result)
    result = NUMBER_AMOUNT_RE.sub("[AMOUNT]", result)
    return result

# print(sanitise("Alice paid $100 to Bob on January 1st, 2023. They met in New York."))
