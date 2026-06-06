import json, csv, sys, re, os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import anthropic
from rich.console import Console
from rich.table import Table
from rich import box

load_dotenv(find_dotenv(usecwd=True))

console = Console()

CACHE_PATH = Path(__file__).with_name("cache.json")
CONFIDENCE_THRESHOLD = 0.7
MODEL = "claude-haiku-4-5"

# ── Normalization ─────────────────────────────────────────────────────────────
# Strip everything that makes the same merchant look different across statements

def normalize(desc: str) -> str:
    s = desc.upper()
    # Bank-injected prefixes — strip before anything else so the merchant name is exposed
    s = re.sub(r'^APLPAY\s+', '', s)                     # Apple Pay: "APLPAY TST*..." → "TST*..."
    s = re.sub(r'^APPLEPAY\s+', '', s)                   # alternate Apple Pay spelling
    s = re.sub(r'^APPLE PAY\s+', '', s)
    s = re.sub(r'^GPAY\s+', '', s)                       # Google Pay
    s = re.sub(r'^GOOGLE\s*PAY\s+', '', s)
    s = re.sub(r'^ACH[:\s]\s*', '', s)                   # ACH: prefix
    s = re.sub(r'^ORIG:\s*', '', s)                      # ACH originator tag
    s = re.sub(r'^CO:\s*', '', s)                        # ACH company tag: "CO: STARBUCKS"
    s = re.sub(r'^CID:\s*\S+\s*', '', s)                 # Customer ID tag
    s = re.sub(r'^POS:?PURCHASE\s*', '', s)              # POS PURCHASE prefix
    s = re.sub(r'^POS\s*DEBIT\s*', '', s)                # POS DEBIT prefix
    s = re.sub(r'^POS\s*-\s*', '', s)                    # POS - prefix
    s = re.sub(r'^VISA\s+DDA\s+(?:PUR|RFD|PMT)\s*', '', s)  # "VISA DDA PUR STARBUCKS"
    s = re.sub(r'^CKCD\s+(?:PUR|RFD)\s*', '', s)        # Chase: "CKCD PUR STARBUCKS"
    s = re.sub(r'^WEB\s*BRANCH:\s*', '', s)              # Online banking prefix
    s = re.sub(r'^WEB\s*(?:PMNT?|PMT):\s*', '', s)      # Web payment prefix
    s = re.sub(r'^ECOM\b\s*:?\s*', '', s)                # Ecom purchase tag
    s = re.sub(r'^ONLINE\s+PURCHASE\s+', '', s)          # Generic online prefix
    s = re.sub(r'^CHECKCARD\s+', '', s)                  # Debit card prefix
    s = re.sub(r'^DEBIT\s+CARD\s+', '', s)               # "DEBIT CARD STARBUCKS"
    s = re.sub(r'^DEBIT\s+', '', s)                      # bare DEBIT prefix
    s = re.sub(r'^PURCHASE\s+', '', s)                   # Generic purchase prefix
    s = re.sub(r'^RECURRING\s+', '', s)                  # Recurring marker
    s = re.sub(r'^DBA\s+', '', s)                        # "DBA MERCHANT NAME"
    # Payment processor prefixes (SQ *, PP *, etc.)
    s = re.sub(r'\bSQ\s*\*\s*', '', s)                   # Square: "SQ *BLUE BOTTLE" → "BLUE BOTTLE"
    s = re.sub(r'\bPP\s*\*\s*', '', s)                   # PayPal: "PP *ETSY" → "ETSY"
    s = re.sub(r'\bSP\s*\*\s*', '', s)                   # Stripe
    s = re.sub(r'\bTST\s*\*\s*', 'TST ', s)              # Toast POS — keep TST for dining rule
    s = re.sub(r'\bDD\s*\*\s*', '', s)                   # DoorDash direct: "DD *DOORDASH"
    s = re.sub(r'\bPY\s*\*\s*', '', s)                   # Pay: "PY *CRUMBL"
    s = re.sub(r'\s*\*\s*', ' ', s)                      # Other * separators
    # Merchant / terminal IDs injected mid-string
    s = re.sub(r'\bMID:\s*\S+', '', s)                   # Merchant ID: "MID:9876543"
    s = re.sub(r'\bTID:\s*\S+', '', s)                   # Terminal ID
    s = re.sub(r'\bREF#\s*\S+', '', s)                   # Reference number
    s = re.sub(r'\bXXXX\d{4}\b', '', s)                  # Masked card suffix: "XXXX1234"
    # Noise stripping
    s = re.sub(r'\s+#\d+', '', s)                        # Store numbers: "#455"
    s = re.sub(r'#\d+', '', s)                           # Store numbers directly attached: "WAWA#123"
    s = re.sub(r'\s+\d{5,}', '', s)                      # Long numeric IDs
    s = re.sub(r'\.COM\b', '', s)                        # Domain: "NETFLIX.COM" → "NETFLIX"
    s = re.sub(r'\.NET\b', '', s)
    s = re.sub(r'\.ORG\b', '', s)
    s = re.sub(r'\.IO\b', '', s)
    s = re.sub(r'\s+\d{3}-\S+', '', s)                   # Phone suffixes: "800-COMCAST"
    # Trailing legal suffixes before location stripping
    s = re.sub(r'\s+\b(?:INC|LLC|CORP|LTD|CO|LP)\b\.?$', '', s)
    # Location / state suffix patterns banks append
    s = re.sub(r'\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?.*$', '', s)   # "MADISON WI 53703" or "WI 53703-1234"
    s = re.sub(r'\s+[A-Z]{2}\s*$', '', s)                      # trailing state abbrev "STARBUCKS WI"
    # Date/time injected by some banks
    s = re.sub(r'\s+\d{2}/\d{2}/\d{2,4}(?:\s+\d{2}:\d{2})?', '', s)
    return ' '.join(s.split())


# ── Rule table ────────────────────────────────────────────────────────────────
# (compiled_regex, category) — checked in order, first match wins
# Ordered so more-specific patterns come first (e.g. UBER EATS before UBER)

RULES: list[tuple[re.Pattern, str]] = [
    # ── Income ──────────────────────────────────────────────────────────────
    (re.compile(r'\bPAYROLL\b'),                        'Income'),
    (re.compile(r'\bDIRECT DEP\b'),                     'Income'),
    (re.compile(r'\bDIR DEP\b'),                        'Income'),
    (re.compile(r'\bACH DEP\b'),                        'Income'),
    (re.compile(r'\bTAX REFUND\b'),                     'Income'),

    # ── Peer transfers ───────────────────────────────────────────────────────
    (re.compile(r'\bZELLE\b'),                          'Zelle'),
    (re.compile(r'\bVENMO\b'),                          'Transfers'),
    (re.compile(r'\bCASH APP\b'),                       'Transfers'),
    (re.compile(r'\bPAYPAL\b'),                         'Transfers'),
    (re.compile(r'\bWIRE TRANSFER\b'),                  'Transfers'),
    (re.compile(r'\bACH TRANSFER\b'),                   'Transfers'),
    (re.compile(r'\bONLINE TRANSFER\b'),                'Transfers'),

    # ── Credit card payments ─────────────────────────────────────────────────
    (re.compile(r'\bCREDIT CARD PAYMENT\b'),            'Credit Card Bill'),
    (re.compile(r'\bCC PAYMENT\b'),                     'Credit Card Bill'),
    (re.compile(r'\bAUTO PAY\b.*\bCC\b'),               'Credit Card Bill'),

    # ── Transport ────────────────────────────────────────────────────────────
    # Delivery apps MUST come before their parent brands
    (re.compile(r'\bUBER\s*EATS\b'),                    'Dining'),
    (re.compile(r'\bUBER\b'),                           'Transport'),
    (re.compile(r'\bLYFT\b'),                           'Transport'),
    (re.compile(r'\bCOACH USA\b'),                      'Transport'),
    (re.compile(r'\bGREYHOUND\b'),                      'Transport'),
    (re.compile(r'\bAMTRAK\b'),                         'Transport'),
    (re.compile(r'\bSPIRIT AIR\b'),                     'Transport'),
    (re.compile(r'\bSOUTHWEST\b'),                      'Transport'),
    (re.compile(r'\bDELTA AIR\b'),                      'Transport'),
    (re.compile(r'\bUNITED AIR\b'),                     'Transport'),
    (re.compile(r'\bAMERICAN AIR\b'),                   'Transport'),
    (re.compile(r'\bFRONTIER AIR\b'),                   'Transport'),
    (re.compile(r'\bJETBLUE\b'),                        'Transport'),
    (re.compile(r'\bALASKA AIR\b'),                     'Transport'),
    (re.compile(r'\bHAWAIIAN AIR\b'),                   'Transport'),
    (re.compile(r'\bALLEGIANT\b'),                      'Transport'),
    (re.compile(r'\bEXPEDIA\b'),                        'Transport'),
    (re.compile(r'\bPRICELINE\b'),                      'Transport'),
    (re.compile(r'\bKAYAK\b'),                          'Transport'),
    (re.compile(r'\bHERTZ\b'),                          'Transport'),
    (re.compile(r'\bENTERPRISE RENT\b'),                'Transport'),
    (re.compile(r'\bNATIONAL CAR\b'),                   'Transport'),
    (re.compile(r'\bAVIS\b'),                           'Transport'),
    (re.compile(r'\bBUDGET RENT\b'),                    'Transport'),
    (re.compile(r'\bTHRIFTY\b'),                        'Transport'),
    (re.compile(r'\bDOLLAR RENT\b'),                    'Transport'),
    (re.compile(r'\bZIPCAR\b'),                         'Transport'),
    (re.compile(r'\bTURO\b'),                           'Transport'),
    (re.compile(r'\bSCOOTER\b'),                        'Transport'),
    (re.compile(r'\bLIME\b'),                           'Transport'),
    (re.compile(r'\bBIRD\b'),                           'Transport'),
    (re.compile(r'\bMTA\b'),                            'Transport'),
    (re.compile(r'\bTRANSIT\b'),                        'Transport'),
    (re.compile(r'\bPARKING\b'),                        'Transport'),
    (re.compile(r'\bSPOTHERO\b'),                       'Transport'),
    (re.compile(r'\bPARKMOBILE\b'),                     'Transport'),
    (re.compile(r'\bEZPASS\b'),                         'Transport'),
    (re.compile(r'\bTOLL\b'),                           'Transport'),
    (re.compile(r'\bGAS\s+STATION\b'),                  'Transport'),
    (re.compile(r'\bCHEVRON\b'),                        'Transport'),
    (re.compile(r'\bSHELL\b'),                          'Transport'),
    (re.compile(r'\bEXXON\b'),                          'Transport'),
    (re.compile(r'\bMOBIL\b'),                          'Transport'),
    (re.compile(r'\bBP\b'),                             'Transport'),
    (re.compile(r'\bSUNOCO\b'),                         'Transport'),
    (re.compile(r'\bCITGO\b'),                          'Transport'),
    (re.compile(r'\bKWIK TRIP\b'),                      'Transport'),
    (re.compile(r'\bCASEYS\b'),                         'Transport'),
    (re.compile(r'\bMURPHY USA\b'),                     'Transport'),
    (re.compile(r'\bPILOT TRAVEL\b'),                   'Transport'),
    (re.compile(r'\bFLYING J\b'),                       'Transport'),
    (re.compile(r'\bWAWA\b'),                           'Transport'),
    (re.compile(r'\bSHEETZ\b'),                         'Transport'),

    # ── Shopping / Retail ────────────────────────────────────────────────────
    # Amazon Prime must come before generic AMAZON → Shopping rule
    (re.compile(r'\bAMAZON PRIME\b'),                   'Subscriptions'),
    (re.compile(r'\bAMZN\b'),                           'Shopping'),
    (re.compile(r'\bAMAZON\b'),                         'Shopping'),
    (re.compile(r'\bTARGET\b'),                         'Shopping'),
    (re.compile(r'\bWALMART\b'),                        'Shopping'),
    (re.compile(r'\bWALMART\b'),                        'Shopping'),
    (re.compile(r'\bUNIQLO\b'),                         'Shopping'),
    (re.compile(r'\bBEST BUY\b'),                       'Shopping'),
    (re.compile(r'\bETSY\b'),                           'Shopping'),
    (re.compile(r'\bEBAY\b'),                           'Shopping'),
    (re.compile(r'\bSHEIN\b'),                          'Shopping'),
    (re.compile(r'\bTEMU\b'),                           'Shopping'),
    (re.compile(r'\bZARA\b'),                           'Shopping'),
    (re.compile(r'\bH&M\b'),                            'Shopping'),
    (re.compile(r'\bNIKE\b'),                           'Shopping'),
    (re.compile(r'\bADIDAS\b'),                         'Shopping'),
    (re.compile(r'\bFOOT LOCKER\b'),                    'Shopping'),
    (re.compile(r'\bFINISH LINE\b'),                    'Shopping'),
    (re.compile(r'\bDICKS SPORTING\b'),                 'Shopping'),
    (re.compile(r'\bHOME DEPOT\b'),                     'Shopping'),
    (re.compile(r'\bLOWES\b'),                          'Shopping'),
    (re.compile(r'\bIKEA\b'),                           'Shopping'),
    (re.compile(r'\bWAYFAIR\b'),                        'Shopping'),
    (re.compile(r'\bBATH BODY\b'),                      'Shopping'),
    (re.compile(r'\bBBW\b'),                            'Shopping'),
    (re.compile(r'\bVICTORIA SECRET\b'),                'Shopping'),
    (re.compile(r'\bSEPHORA\b'),                        'Shopping'),
    (re.compile(r'\bULTA\b'),                           'Shopping'),
    (re.compile(r'\bMACYS\b'),                          'Shopping'),
    (re.compile(r'\bNORDSTROM\b'),                      'Shopping'),
    (re.compile(r'\bBARNES NOBLE\b'),                   'Shopping'),
    (re.compile(r'\bBOOKS\b.*\bMILLION\b'),            'Shopping'),
    (re.compile(r'\bAPPLE STORE\b'),                    'Shopping'),
    (re.compile(r'\bAPPLE COM\b'),                      'Shopping'),  # Apple.com (non-subscription)
    (re.compile(r'\bMICROSOFT STORE\b'),                'Shopping'),
    (re.compile(r'\bGAP\b'),                            'Shopping'),
    (re.compile(r'\bOLD NAVY\b'),                       'Shopping'),
    (re.compile(r'\bBANANA REPUBLIC\b'),                'Shopping'),
    (re.compile(r'\bJ CREW\b'),                         'Shopping'),
    (re.compile(r'\bJ\.CREW\b'),                        'Shopping'),
    (re.compile(r'\bAMERICAN EAGLE\b'),                 'Shopping'),
    (re.compile(r'\bAEO\b'),                            'Shopping'),   # American Eagle Outfitters
    (re.compile(r'\bHOLLISTER\b'),                      'Shopping'),
    (re.compile(r'\bABERCROMBIE\b'),                    'Shopping'),
    (re.compile(r'\bANF\b'),                            'Shopping'),   # Abercrombie & Fitch
    (re.compile(r'\bURBAN OUTFITTERS\b'),               'Shopping'),
    (re.compile(r'\bANTHROPOLOGIE\b'),                 'Shopping'),
    (re.compile(r'\bFREE PEOPLE\b'),                    'Shopping'),
    (re.compile(r'\bEXPRESS\b'),                        'Shopping'),
    (re.compile(r'\bFOREVER 21\b'),                     'Shopping'),
    (re.compile(r'\bLULULEMON\b'),                      'Shopping'),
    (re.compile(r'\bATHLETA\b'),                        'Shopping'),
    (re.compile(r'\bNORDSTROM RACK\b'),                 'Shopping'),
    (re.compile(r'\bTJ\s*MAXX\b'),                      'Shopping'),
    (re.compile(r'\bTJX\b'),                            'Shopping'),
    (re.compile(r'\bMARSHALLS\b'),                      'Shopping'),
    (re.compile(r'\bROSS\b'),                           'Shopping'),
    (re.compile(r'\bBURLINGTON\b'),                     'Shopping'),
    (re.compile(r'\bFIVE BELOW\b'),                     'Shopping'),
    (re.compile(r'\bDOLLAR TREE\b'),                    'Shopping'),
    (re.compile(r'\bDOLLAR GENERAL\b'),                 'Shopping'),
    (re.compile(r'\bFAMILY DOLLAR\b'),                  'Shopping'),
    (re.compile(r'\bGAMESTOP\b'),                       'Shopping'),
    (re.compile(r'\bCHEWY\b'),                          'Shopping'),
    (re.compile(r'\bPETCO\b'),                          'Shopping'),
    (re.compile(r'\bPETSMART\b'),                       'Shopping'),
    (re.compile(r'\bOVERSTOCK\b'),                      'Shopping'),
    (re.compile(r'\bCRATE\s*(?:AND|&|N)?\s*BARREL\b'), 'Shopping'),
    (re.compile(r'\bCB2\b'),                            'Shopping'),
    (re.compile(r'\bPOTTERY BARN\b'),                   'Shopping'),
    (re.compile(r'\bWILLIAMS SONOMA\b'),                'Shopping'),
    (re.compile(r'\bBED BATH\b'),                       'Shopping'),
    (re.compile(r'\bBIG LOTS\b'),                       'Shopping'),
    (re.compile(r'\bTUESDAY MORNING\b'),                'Shopping'),
    (re.compile(r'\bOFFICE DEPOT\b'),                   'Shopping'),
    (re.compile(r'\bSTAPLES\b'),                        'Shopping'),
    (re.compile(r'\bPETER MILLAR\b'),                   'Shopping'),
    (re.compile(r'\bRALPH LAUREN\b'),                   'Shopping'),

    # ── Groceries ────────────────────────────────────────────────────────────
    (re.compile(r'\bWHOLE FOODS\b'),                    'Groceries'),
    (re.compile(r'\bKROGER\b'),                         'Groceries'),
    (re.compile(r'\bALDI\b'),                           'Groceries'),
    (re.compile(r'\bTRADER JOE\b'),                     'Groceries'),
    (re.compile(r'\bSAFEWAY\b'),                        'Groceries'),
    (re.compile(r'\bPUBLIX\b'),                         'Groceries'),
    (re.compile(r'\bH-E-B\b'),                          'Groceries'),
    (re.compile(r'\bHEB\b'),                            'Groceries'),
    (re.compile(r'\bWEGMANS\b'),                        'Groceries'),
    (re.compile(r'\bMEIJER\b'),                         'Groceries'),
    (re.compile(r'\bSTOP SHOP\b'),                      'Groceries'),
    (re.compile(r'\bGIANT\b'),                          'Groceries'),
    (re.compile(r'\bHARRIS TEETER\b'),                  'Groceries'),
    (re.compile(r'\bSPROUTS\b'),                        'Groceries'),
    (re.compile(r'\bFOOD LION\b'),                      'Groceries'),
    (re.compile(r'\bMARKET BASKET\b'),                  'Groceries'),
    (re.compile(r'\bSHOPRITE\b'),                       'Groceries'),
    (re.compile(r'\bFRESH MARKET\b'),                   'Groceries'),
    (re.compile(r'\bNATURE BASKET\b'),                  'Groceries'),
    (re.compile(r'\bCOSTCO\b'),                         'Groceries'),
    (re.compile(r'\bSAMS CLUB\b'),                      'Groceries'),
    (re.compile(r'\bBJS WHOLESALE\b'),                  'Groceries'),
    (re.compile(r'\bWINN DIXIE\b'),                     'Groceries'),
    (re.compile(r'\bWINNDIXIE\b'),                      'Groceries'),
    (re.compile(r'\bINGLES\b'),                         'Groceries'),
    (re.compile(r'\bPRICE CHOPPER\b'),                  'Groceries'),
    (re.compile(r'\bWINCO\b'),                          'Groceries'),
    (re.compile(r'\bFOOD 4 LESS\b'),                    'Groceries'),
    (re.compile(r'\bSTATER BROS\b'),                    'Groceries'),
    (re.compile(r'\bRALPHS\b'),                         'Groceries'),
    (re.compile(r'\bVONS\b'),                           'Groceries'),
    (re.compile(r'\bPAVILIONS\b'),                      'Groceries'),
    (re.compile(r'\bSCHNUCKS\b'),                       'Groceries'),
    (re.compile(r'\bPIGGLY WIGGLY\b'),                  'Groceries'),
    (re.compile(r'\bSAVE A LOT\b'),                     'Groceries'),
    (re.compile(r'\bGROCERY OUTLET\b'),                 'Groceries'),
    (re.compile(r'\bNATURAL GROCERS\b'),                'Groceries'),
    (re.compile(r'\bEARTH FARE\b'),                     'Groceries'),
    (re.compile(r'\bLUCKY SUPERMARKET\b'),              'Groceries'),
    (re.compile(r'\bFIESTA MART\b'),                    'Groceries'),
    (re.compile(r'\bBROOKSHIRE\b'),                     'Groceries'),
    (re.compile(r'\bDILLONS\b'),                        'Groceries'),
    (re.compile(r'\bSMITHS FOOD\b'),                    'Groceries'),
    (re.compile(r'\bFRED MEYER\b'),                     'Groceries'),
    (re.compile(r'\bQFC\b'),                            'Groceries'),
    (re.compile(r'\bACME\s+MARKET\b'),                  'Groceries'),
    (re.compile(r'\bLIDL\b'),                           'Groceries'),
    (re.compile(r'\bNETTO\b'),                          'Groceries'),

    # ── Dining ───────────────────────────────────────────────────────────────
    (re.compile(r'\bTST\b'),                            'Dining'),   # Toast restaurant POS
    (re.compile(r'\bSTARBUCKS\b'),                      'Dining'),
    (re.compile(r'\bDUNKIN\b'),                         'Dining'),
    (re.compile(r'\bRAISING CANE'),                     'Dining'),   # handles "RAISING CANESMADISON"
    (re.compile(r'\bDOORDASH\b'),                       'Dining'),
    (re.compile(r'\bGRUBHUB\b'),                        'Dining'),
    (re.compile(r'\bCHIPOTLE\b'),                       'Dining'),
    (re.compile(r'\bCANTEEN\b'),                        'Dining'),
    (re.compile(r'\bMCDONALD\b'),                       'Dining'),
    (re.compile(r'\bMCDS\b'),                           'Dining'),
    (re.compile(r'\bBURGER KING\b'),                    'Dining'),
    (re.compile(r'\bWENDYS\b'),                         'Dining'),
    (re.compile(r'\bTACO BELL\b'),                      'Dining'),
    (re.compile(r'\bCHICK.FIL.A\b'),                   'Dining'),
    (re.compile(r'\bCFA\b'),                            'Dining'),
    (re.compile(r'\bPANERA\b'),                         'Dining'),
    (re.compile(r'\bSUBWAY\b'),                         'Dining'),
    (re.compile(r'\bJERSEY MIKES\b'),                   'Dining'),
    (re.compile(r'\bJIMMY JOHNS\b'),                    'Dining'),
    (re.compile(r'\bFIVE GUYS\b'),                      'Dining'),
    (re.compile(r'\bSHAKE SHACK\b'),                    'Dining'),
    (re.compile(r'\bIN-N-OUT\b'),                       'Dining'),
    (re.compile(r'\bWHATABURGER\b'),                    'Dining'),
    (re.compile(r'\bSONIC\b'),                          'Dining'),
    (re.compile(r'\bARBYS\b'),                          'Dining'),
    (re.compile(r'\bPIZZA HUT\b'),                      'Dining'),
    (re.compile(r'\bDOMINOS\b'),                        'Dining'),
    (re.compile(r'\bPAPA JOHNS\b'),                     'Dining'),
    (re.compile(r'\bLITTLE CAESARS\b'),                 'Dining'),
    (re.compile(r'\bWINGSTOP\b'),                       'Dining'),
    (re.compile(r'\bCHILIS\b'),                         'Dining'),
    (re.compile(r'\bAPPLEBEES\b'),                      'Dining'),
    (re.compile(r'\bOLIVE GARDEN\b'),                   'Dining'),
    (re.compile(r'\bRED LOBSTER\b'),                    'Dining'),
    (re.compile(r'\bTEXAS ROADHOUSE\b'),                'Dining'),
    (re.compile(r'\bOUTBACK\b'),                        'Dining'),
    (re.compile(r'\bDENNYS\b'),                         'Dining'),
    (re.compile(r'\bIHOP\b'),                           'Dining'),
    (re.compile(r'\bCRACKER BARREL\b'),                 'Dining'),
    (re.compile(r'\bSWEETGREEN\b'),                     'Dining'),
    (re.compile(r'\bCAVA\b'),                           'Dining'),
    (re.compile(r'\bPOPEYES\b'),                        'Dining'),
    (re.compile(r'\bPOPEYE\b'),                         'Dining'),
    (re.compile(r'\bJACK IN THE BOX\b'),                'Dining'),
    (re.compile(r'\bHARDEES\b'),                        'Dining'),
    (re.compile(r'\bCARLS JR\b'),                       'Dining'),
    (re.compile(r'\bCARL\'S JR\b'),                     'Dining'),
    (re.compile(r'\bDEL TACO\b'),                       'Dining'),
    (re.compile(r'\bCULVERS\b'),                        'Dining'),
    (re.compile(r'\bWHITE CASTLE\b'),                   'Dining'),
    (re.compile(r'\bSTEAK\s*N\s*SHAKE\b'),              'Dining'),
    (re.compile(r'\bWAFFLE HOUSE\b'),                   'Dining'),
    (re.compile(r'\bBOJANGLES\b'),                      'Dining'),
    (re.compile(r'\bZAXBYS\b'),                         'Dining'),
    (re.compile(r'\bCOOK OUT\b'),                       'Dining'),
    (re.compile(r'\bCOOKOUT\b'),                        'Dining'),
    (re.compile(r'\bSMASHBURGER\b'),                    'Dining'),
    (re.compile(r'\bFREDDYS\b'),                        'Dining'),
    (re.compile(r'\bFREDDY\'S\b'),                      'Dining'),
    (re.compile(r'\bGOLDEN CORRAL\b'),                  'Dining'),
    (re.compile(r'\bQDOBA\b'),                          'Dining'),
    (re.compile(r'\bMOES\b'),                           'Dining'),
    (re.compile(r'\bNOODLES\b'),                        'Dining'),
    (re.compile(r'\bJASONS DELI\b'),                    'Dining'),
    (re.compile(r'\bEINSTEIN BAGEL\b'),                 'Dining'),
    (re.compile(r'\bBRUEGGERS\b'),                      'Dining'),
    (re.compile(r'\bPOTBELLY\b'),                       'Dining'),
    (re.compile(r'\bCARIBOU COFFEE\b'),                 'Dining'),
    (re.compile(r'\bPIZZA\b'),                          'Dining'),
    (re.compile(r'\bSANDWICH\b'),                       'Dining'),
    (re.compile(r'\bICE CREAM\b'),                      'Dining'),
    (re.compile(r'\bCREAMERY\b'),                       'Dining'),
    (re.compile(r'\bSCOOP\b'),                          'Dining'),
    (re.compile(r'\bTAPROOM\b'),                        'Dining'),
    (re.compile(r'\bBREWERY\b'),                        'Dining'),
    (re.compile(r'\bBREWPUB\b'),                        'Dining'),
    (re.compile(r'\bWINERY\b'),                         'Dining'),
    (re.compile(r'\bBAR &\b'),                          'Dining'),
    (re.compile(r'\bPOKE\b'),                           'Dining'),
    (re.compile(r'\bBOBA\b'),                           'Dining'),
    (re.compile(r'\bNAF NAF\b'),                        'Dining'),
    (re.compile(r'\bPINKUS\b'),                         'Dining'),   # Pinkus Market (local)
    (re.compile(r'\bMADISTAN\b'),                       'Dining'),   # local
    (re.compile(r'\bDUBURGER\b'),                       'Dining'),
    (re.compile(r'\bORD WOW BAO\b'),                    'Dining'),
    (re.compile(r'\bBAO\b'),                            'Dining'),
    (re.compile(r'\bPHO\b'),                            'Dining'),
    (re.compile(r'\bSUSHI\b'),                          'Dining'),
    (re.compile(r'\bRAMEN\b'),                          'Dining'),
    (re.compile(r'\bBURRITO\b'),                        'Dining'),
    (re.compile(r'\bGRILL\b'),                          'Dining'),
    (re.compile(r'\bBISTRO\b'),                         'Dining'),
    (re.compile(r'\bCAFE\b'),                           'Dining'),
    (re.compile(r'\bBAKERY\b'),                         'Dining'),
    (re.compile(r'\bCOFFEE\b'),                         'Dining'),
    (re.compile(r'\bSMOOTHIE\b'),                       'Dining'),
    (re.compile(r'\bJUICE BAR\b'),                      'Dining'),
    (re.compile(r'\bRESTAURANT\b'),                     'Dining'),

    # ── Subscriptions ────────────────────────────────────────────────────────
    (re.compile(r'\bNETFLIX\b'),                        'Subscriptions'),
    (re.compile(r'\bSPOTIFY\b'),                        'Subscriptions'),
    (re.compile(r'\bHULU'),                             'Subscriptions'),
    (re.compile(r'\bDISNEY\b'),                         'Subscriptions'),
    (re.compile(r'\bDISNEY PLUS\b'),                    'Subscriptions'),
    (re.compile(r'\bHBO\b'),                            'Subscriptions'),
    (re.compile(r'\bMAX\b.*\bBIL\b'),                   'Subscriptions'),
    (re.compile(r'\bPEACOCK\b'),                        'Subscriptions'),
    (re.compile(r'\bPARAMOUNT\b'),                      'Subscriptions'),
    (re.compile(r'\bYOUTUBE\b'),                        'Subscriptions'),
    (re.compile(r'\bYT PREMIUM\b'),                     'Subscriptions'),
    (re.compile(r'\bTWITCH\b'),                         'Subscriptions'),
    (re.compile(r'\bSONYLIV\b'),                        'Subscriptions'),
    (re.compile(r'\bOPENAI\b'),                         'Subscriptions'),
    (re.compile(r'\bCHATGPT\b'),                        'Subscriptions'),
    (re.compile(r'\bAPPLE\b.*\bBIL'),                   'Subscriptions'),   # APPLE.COM/BILL
    (re.compile(r'\bITUNES\b'),                         'Subscriptions'),
    (re.compile(r'\bAPPLE MUSIC\b'),                    'Subscriptions'),
    (re.compile(r'\bAPPLE TV\b'),                       'Subscriptions'),
    (re.compile(r'\bMICROSOFT 365\b'),                  'Subscriptions'),
    (re.compile(r'\bMICROSOFT 36\b'),                   'Subscriptions'),
    (re.compile(r'\bXBOX\b'),                           'Subscriptions'),
    (re.compile(r'\bGAME PASS\b'),                      'Subscriptions'),
    (re.compile(r'\bPLAYSTATION\b'),                    'Subscriptions'),
    (re.compile(r'\bPSN\b'),                            'Subscriptions'),
    (re.compile(r'\bNINTENDO\b'),                       'Subscriptions'),
    (re.compile(r'\bSTEAM\b'),                          'Subscriptions'),
    (re.compile(r'\bADOBE\b'),                          'Subscriptions'),
    (re.compile(r'\bDROPBOX\b'),                        'Subscriptions'),
    (re.compile(r'\bGOOGLE ONE\b'),                     'Subscriptions'),
    (re.compile(r'\bGOOGLE STOR\b'),                    'Subscriptions'),
    (re.compile(r'\bICLOUD\b'),                         'Subscriptions'),
    (re.compile(r'\bNYT\b'),                            'Subscriptions'),   # NY Times
    (re.compile(r'\bWASHINGTON POST\b'),                'Subscriptions'),
    (re.compile(r'\bWALL ST JOUR\b'),                   'Subscriptions'),
    (re.compile(r'\bDUOLINGO\b'),                       'Subscriptions'),
    (re.compile(r'\bBEETLE\b'),                         'Subscriptions'),
    (re.compile(r'\bAUDIBLE\b'),                        'Subscriptions'),
    (re.compile(r'\bKINDLE\b'),                         'Subscriptions'),
    (re.compile(r'\bFUBOTV\b'),                         'Subscriptions'),
    (re.compile(r'\bFUBO\b'),                           'Subscriptions'),
    (re.compile(r'\bSLING\b'),                          'Subscriptions'),
    (re.compile(r'\bESPN PLUS\b'),                      'Subscriptions'),
    (re.compile(r'\bESPN\+\b'),                         'Subscriptions'),
    (re.compile(r'\bSHOWTIME\b'),                       'Subscriptions'),
    (re.compile(r'\bSTARZ\b'),                          'Subscriptions'),
    (re.compile(r'\bCRUNCHYROLL\b'),                    'Subscriptions'),
    (re.compile(r'\bFUNIMATION\b'),                     'Subscriptions'),
    (re.compile(r'\bPANDORA\b'),                        'Subscriptions'),
    (re.compile(r'\bTIDAL\b'),                          'Subscriptions'),
    (re.compile(r'\bDEEZER\b'),                         'Subscriptions'),
    (re.compile(r'\bCURIOSITY STREAM\b'),               'Subscriptions'),
    (re.compile(r'\bMASTERCLASS\b'),                    'Subscriptions'),
    (re.compile(r'\bMIDJOURNEY\b'),                     'Subscriptions'),
    (re.compile(r'\bGITHUB\b'),                         'Subscriptions'),
    (re.compile(r'\bNOTION\b'),                         'Subscriptions'),
    (re.compile(r'\bSLACK\b'),                          'Subscriptions'),
    (re.compile(r'\bZOOM\b'),                           'Subscriptions'),
    (re.compile(r'\bLINKEDIN\b'),                       'Subscriptions'),
    (re.compile(r'\bSUBSTACK\b'),                       'Subscriptions'),
    (re.compile(r'\bPATREON\b'),                        'Subscriptions'),

    # ── Health & Pharmacy ────────────────────────────────────────────────────
    (re.compile(r'\bWALGREEN'),                         'Health'),
    (re.compile(r'\bCVS\b'),                            'Health'),
    (re.compile(r'\bRITE AID\b'),                       'Health'),
    (re.compile(r'\bDUANE READE\b'),                    'Health'),
    (re.compile(r'\bPHARMACY\b'),                       'Health'),
    (re.compile(r'\bPLANNED PARENT\b'),                 'Health'),
    (re.compile(r'\bGYM\b'),                            'Health'),
    (re.compile(r'\bFITNESS\b'),                        'Health'),
    (re.compile(r'\bPLANET FITNESS\b'),                 'Health'),
    (re.compile(r'\bGOLD\'S GYM\b'),                    'Health'),
    (re.compile(r'\bCRUNCH\b'),                         'Health'),
    (re.compile(r'\bEQUINOX\b'),                        'Health'),
    (re.compile(r'\bANYTIME FITNESS\b'),                'Health'),
    (re.compile(r'\bLA FITNESS\b'),                     'Health'),
    (re.compile(r'\b24\s*HOUR\s*FITNESS\b'),            'Health'),
    (re.compile(r'\b24HF\b'),                           'Health'),
    (re.compile(r'\bORANGETHEORY\b'),                   'Health'),
    (re.compile(r'\bF45\b'),                            'Health'),
    (re.compile(r'\bPELOTON\b'),                        'Health'),
    (re.compile(r'\bPURE BARRE\b'),                     'Health'),
    (re.compile(r'\bBLINK FITNESS\b'),                  'Health'),
    (re.compile(r'\bSNAP FITNESS\b'),                   'Health'),
    (re.compile(r'\bLIFE TIME\b'),                      'Health'),
    (re.compile(r'\bLIFETIME FITNESS\b'),               'Health'),
    (re.compile(r'\bUFC GYM\b'),                        'Health'),
    (re.compile(r'\bRETRO FITNESS\b'),                  'Health'),
    (re.compile(r'\bCROSSFIT\b'),                       'Health'),
    (re.compile(r'\bSPINNING\b'),                       'Health'),
    (re.compile(r'\bPILATES\b'),                        'Health'),
    (re.compile(r'\bNUTRITION\b'),                      'Health'),
    (re.compile(r'\bCHIROPRACTIC\b'),                   'Health'),
    (re.compile(r'\bTHERAPY\b'),                        'Health'),
    (re.compile(r'\bVISION\b'),                         'Health'),
    (re.compile(r'\bYOGA\b'),                           'Health'),
    (re.compile(r'\bDENTAL\b'),                         'Health'),
    (re.compile(r'\bOPTICAL\b'),                        'Health'),
    (re.compile(r'\bHOSPITAL\b'),                       'Health'),
    (re.compile(r'\bCLINIC\b'),                         'Health'),
    (re.compile(r'\bMEDICAL\b'),                        'Health'),
    (re.compile(r'\bHEALTH\b'),                         'Health'),
    (re.compile(r'\bINSURANCE\b'),                      'Health'),

    # ── Entertainment ────────────────────────────────────────────────────────
    (re.compile(r'\bAMC\b'),                            'Entertainment'),
    (re.compile(r'\bREGAL\b'),                          'Entertainment'),
    (re.compile(r'\bCINEMARK\b'),                       'Entertainment'),
    (re.compile(r'\bFANDAN\b'),                         'Entertainment'),   # Fandango
    (re.compile(r'\bEVENTBRITE\b'),                     'Entertainment'),
    (re.compile(r'\bSTUBHUB\b'),                        'Entertainment'),
    (re.compile(r'\bTICKETMASTER\b'),                   'Entertainment'),
    (re.compile(r'\bBOWLING\b'),                        'Entertainment'),
    (re.compile(r'\bGOKART\b'),                         'Entertainment'),
    (re.compile(r'\bESCAPE ROOM\b'),                    'Entertainment'),
    (re.compile(r'\bMINIATURE GOLF\b'),                 'Entertainment'),
    (re.compile(r'\bARCADE\b'),                         'Entertainment'),
    (re.compile(r'\bDAVE BUSTERS\b'),                   'Entertainment'),
    (re.compile(r'\bSIX FLAGS\b'),                      'Entertainment'),
    (re.compile(r'\bUNIVERSAL\b'),                      'Entertainment'),
    (re.compile(r'\bDISNEYLAND\b'),                     'Entertainment'),

    # ── Utilities & Housing ──────────────────────────────────────────────────
    (re.compile(r'\bELECTRIC\b'),                       'Utilities'),
    (re.compile(r'\bGAS BILL\b'),                       'Utilities'),
    (re.compile(r'\bWATER BILL\b'),                     'Utilities'),
    (re.compile(r'\bCOMCAST\b'),                        'Utilities'),
    (re.compile(r'\bXFINITY\b'),                        'Utilities'),
    (re.compile(r'\bAT&T\b'),                           'Utilities'),
    (re.compile(r'\bVERIZON\b'),                        'Utilities'),
    (re.compile(r'\bT-MOBILE\b'),                       'Utilities'),
    (re.compile(r'\bT MOBILE\b'),                       'Utilities'),
    (re.compile(r'\bSPRINT\b'),                         'Utilities'),
    (re.compile(r'\bCHARTER\b'),                        'Utilities'),
    (re.compile(r'\bSPECTRUM\b'),                       'Utilities'),
    (re.compile(r'\bINTERNET\b'),                       'Utilities'),
    (re.compile(r'\bRENT\b'),                           'Housing'),
    (re.compile(r'\bMORTGAGE\b'),                       'Housing'),
    (re.compile(r'\bAPARTMENT\b'),                      'Housing'),
    (re.compile(r'\bHOA\b'),                            'Housing'),
    (re.compile(r'\bAIRBNB\b'),                         'Housing'),
    (re.compile(r'\bVRBO\b'),                           'Housing'),

    # ── Education ────────────────────────────────────────────────────────────
    (re.compile(r'\bUNIVERSITY BOOK\b'),                'Education'),
    (re.compile(r'\bBOOK STORE\b'),                     'Education'),
    (re.compile(r'\bCOURSERA\b'),                       'Education'),
    (re.compile(r'\bUDEMY\b'),                          'Education'),
    (re.compile(r'\bLINKEDIN LEARN\b'),                 'Education'),
    (re.compile(r'\bSKILLSHARE\b'),                     'Education'),
    (re.compile(r'\bTUITION\b'),                        'Education'),
    (re.compile(r'\bSTUDENT LOAN\b'),                   'Education'),
]

ALLOWED = {
    "Groceries", "Dining", "Transport", "Shopping", "Utilities", "Housing",
    "Health", "Entertainment", "Subscriptions", "Income", "Transfers",
    "Education", "Zelle", "Credit Card Bill", "Other",
}

# ── Claude system prompt ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a bank transaction categorization engine. Assign each transaction to exactly ONE category from this fixed list:

Groceries, Dining, Transport, Shopping, Utilities, Housing, Health, Entertainment, Subscriptions, Income, Transfers, Education, Zelle, Credit Card Bill, Other

IMPORTANT RULES:
- Bank descriptions are truncated, abbreviated, and often include payment processor prefixes. Use your knowledge of common merchants to decode them.
- SQ * = Square register — could be ANY small business. Look at the name after it: a salon/spa/barbershop → Health; a food truck/cafe/restaurant → Dining; a boutique/market → Shopping.
- TST * = Toast POS (always a restaurant → Dining)
- PP * = PayPal (check the merchant name for the real category)
- VZWRLSS / VZWPREPAID = Verizon Wireless → Utilities
- AMZN MKTP = Amazon Marketplace → Shopping; AMAZON PRIME = → Subscriptions
- Amounts < 0 are expenses, > 0 are income/refunds
- "Other" only for truly unrecognizable descriptions

EXAMPLES of tricky descriptions:
- "SQ *BLUE BOTTLE COFF" → Dining (Blue Bottle Coffee, a coffee chain)
- "SQ *HAIR SALON" → Health (hair salon via Square — NOT Dining despite SQ prefix)
- "SQ *NAIL SPA" → Health (nail salon — same logic)
- "TST* THE LOST DOG" → Dining (Toast POS at a restaurant)
- "AMZN MKTP US" → Shopping (Amazon Marketplace)
- "AMAZON PRIME*AB3CD4EF" → Subscriptions (Amazon Prime membership, not a product purchase)
- "SP * SUBSTACK" → Subscriptions (Substack newsletter)
- "WHOLEFDS MKT 10523 CAMBRIDGE MA" → Groceries (Whole Foods Market)
- "WHOLEFDS #10523" → Groceries (Whole Foods — store number, not an ID)
- "DD *DOORDASH" → Dining (DoorDash food delivery)
- "GOOGLE *GSUITE" → Subscriptions (Google Workspace)
- "VZWRLSS*APOCC VIZPAY" → Utilities (Verizon Wireless bill)
- "PARKWAY DENTAL" → Health (dental office)
- "BP#5642393DEARBORN MI" → Transport (BP gas station)
- "AUDIBLE*AB12CD34" → Subscriptions (Audible audiobook service)
- "WAWA 1234 MEDIA PA" → Transport (Wawa convenience/gas store)
- "CRUNCH FITNESS" → Health (gym membership)
- "INSTACART*WHOLEFDS" → Groceries (Instacart grocery delivery)

Return ONLY a JSON object: {"results": [...]}
Each element: {"id": <int>, "category": "<category>", "confidence": <float 0.0-1.0>}
High confidence (0.9+) when you clearly recognize the merchant. Low confidence (0.5-0.7) when genuinely ambiguous."""


# ── Claude LLM call ───────────────────────────────────────────────────────────

def categorize(txns: list[dict]) -> list[dict]:
    """Call Claude to categorize a batch of transactions the rules didn't match."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    user_content = json.dumps([{"id": t["id"], "desc": t["desc"], "amount": t["amount"]} for t in txns])

    msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = msg.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    return json.loads(raw)["results"]


# ── Cache helpers ─────────────────────────────────────────────────────────────

def load_cache(path: Path) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_cache(path: Path, cache: dict) -> None:
    with open(path, 'w') as f:
        json.dump(cache, f, indent=2)

def get_category_from_cache(entry) -> str:
    if isinstance(entry, dict):
        return entry.get("category", "Other")
    return str(entry)


# ── Rule matching ─────────────────────────────────────────────────────────────

def match_rules(desc: str) -> str | None:
    key = normalize(desc)
    for pattern, category in RULES:
        if pattern.search(key):
            return category
    return None


# ── CLI helpers (unused by web server, kept for standalone use) ───────────────

def load_transactions(path: str) -> list[dict]:
    txns = []
    with open(path) as f:
        for i, row in enumerate(csv.DictReader(f)):
            txns.append({"id": i, "desc": row["description"], "amount": float(row["amount"])})
    return txns

def review_low_confidence(results: dict, txns: list[dict], cache: dict) -> bool:
    by_id = {t["id"]: t for t in txns}
    cats = sorted(ALLOWED)
    cache_dirty = False

    for tid, r in results.items():
        if r["source"] != "llm" or r["confidence"] >= CONFIDENCE_THRESHOLD:
            continue

        t = by_id[tid]
        print(f"\n  ? Low confidence: {t['desc'][:40]}  {t['amount']:>9.2f}")
        print(f"    LLM guessed: {r['category']} ({r['confidence']:.2f})\n")
        for i, c in enumerate(cats, 1):
            print(f"    {i:2}) {c}")

        while True:
            raw = input(f"\n    Accept [{r['category']}] or enter number: ").strip()
            if raw == "":
                chosen = r["category"]
                break
            if raw.isdigit() and 1 <= int(raw) <= len(cats):
                chosen = cats[int(raw) - 1]
                break
            print("    Invalid — enter a number or press Enter to accept.")

        r["category"] = chosen
        cache[normalize(t["desc"])] = chosen
        cache_dirty = True

    return cache_dirty

def print_transactions(results: dict, txns: list[dict]) -> None:
    table = Table(box=box.SIMPLE_HEAVY, show_edge=False)
    table.add_column("Description", max_width=34)
    table.add_column("Amount", justify="right")
    table.add_column("Category", style="cyan")
    table.add_column("Conf", justify="center")
    table.add_column("Src", justify="center", style="dim")

    for t in txns:
        r = results[t["id"]]
        amt_color = "green" if t["amount"] > 0 else "red"
        conf_color = "yellow" if r["confidence"] < CONFIDENCE_THRESHOLD else "white"
        table.add_row(
            t["desc"],
            f"[{amt_color}]{t['amount']:.2f}[/]",
            r["category"],
            f"[{conf_color}]{r['confidence']:.2f}[/]",
            r["source"],
        )
    console.print(table)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "sample.csv"
    txns = load_transactions(path)
    console.print(f"Loaded [bold]{len(txns)}[/] transactions\n")

    cache = load_cache(CACHE_PATH)
    results: dict = {}
    llm_batch: list = []

    for t in txns:
        key = normalize(t["desc"])
        if key in cache:
            results[t["id"]] = {"category": get_category_from_cache(cache[key]), "confidence": 1.0, "source": "cache"}
        else:
            cat = match_rules(t["desc"])
            if cat:
                results[t["id"]] = {"category": cat, "confidence": 1.0, "source": "rule"}
            else:
                llm_batch.append(t)

    if llm_batch:
        console.print(f"Sending [bold]{len(llm_batch)}[/] transactions to Claude...")
        for r in categorize(llm_batch):
            cat = r["category"] if r["category"] in ALLOWED else "Other"
            results[r["id"]] = {"category": cat, "confidence": r["confidence"], "source": "llm"}

    if review_low_confidence(results, txns, cache):
        save_cache(CACHE_PATH, cache)
        console.print("\n[green]  Cache updated.[/]\n")

    print_transactions(results, txns)
