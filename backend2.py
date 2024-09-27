from flask import Flask, request, jsonify, render_template
import re
from collections import defaultdict
import speech_recognition as sr
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Sample legal sections, acts, and corresponding URLs
legal_db = {
    "theft": (["steal", "stole", "stolen", "stealing", "rob", "robbery", "burglary"],
              [("Section 378 IPC", "https://indiankanoon.org/doc/160796086/"),
               ("Section 379 IPC", "https://indiankanoon.org/doc/76417350/")]),
    "assault": (["assaulted", "assaulting", "attack", "attacked", "attacking", "hit", "battery", "injure", "injured", "injuring"],
                [("Section 351 IPC", "https://indiankanoon.org/doc/154563748/"),
                 ("Section 352 IPC", "https://indiankanoon.org/doc/145002594/")]),
    "murder": (["murdered", "murdering", "kill", "killed", "killing", "homicide", "slay", "manslaughter"],
               [("Section 299 IPC", "https://indiankanoon.org/doc/1845877/"),
                ("Section 302 IPC", "https://indiankanoon.org/doc/1120373/")]),
    "fraud": (["cheat", "cheated", "cheating", "deceive", "deceived", "deceiving", "scam", "scammed", "scamming"],
              [("Section 420 IPC", "https://indiankanoon.org/doc/90251163/"),
               ("Section 415 IPC", "https://indiankanoon.org/doc/440556/")]),
    "sedition": (["rebel", "rebelling", "rebellion", "treason", "speech"],
                 [("Section 150 IPC", "https://indiankanoon.org/doc/185213030/")]),
    "defamation": (["slander", "reputation"],
                   [("Section 356 IPC", "https://indiankanoon.org/doc/97252067/")]),
    "mob lynching": (["violence", "group attack", "vigilante", "justice"],
                     [("Section 103(2) IPC", "https://example.com/judgment-101")]),
    "false promise to marry": (["marriage", "marrying", "engagement"],
                               [("Clause 69 IPC", "https://example.com/judgment-69")]),
    "attempt to suicide": (["self-harm", "self harm"],
                          [("Section 224 IPC", "https://example.com/judgment-224")]),
    "gender neutrality": (["gender", "gender equality", "rights"],
                         [("Section 354A IPC", "https://example.com/judgment-354A"),
                          ("Section 354C IPC", "https://example.com/judgment-354C")]),
    "fake news": (["information", "media", "misinformation", "false report"],
                  [("Section 153B IPC", "https://example.com/judgment-153B")]),
    "unnatural sexual offenses": (["consent", "forced sex", "sodomy"],
                                  [("Section 377 IPC", "https://example.com/judgment-377")]),
    "adultery": (["infidelity", "affair", "extramarital", "cheat", "cheated", "cheating", "betrayal"],
                 [("Section 497 IPC", "https://example.com/judgment-497")]),
    "marital rape exception": (["consent", "forced sex", "domestic abuse", "domestic", "harassment"],
                               [("Section 375 IPC", "https://indiankanoon.org/doc/152948503/")]),
    "cruelty by husband or relatives": (["domestic", "torture", "abuse", "domestic abuse", "harassment"],
                                        [("Section 86 IPC", "https://indiankanoon.org/doc/150541962/")]),
    "rape": (["sex", "forced sex", "consent", "sexual violence", "force"],
             [("Section 375 IPC", "https://indiankanoon.org/doc/152948503/"),
              ("Section 376 IPC", "https://indiankanoon.org/doc/110473731/")]),
    "kidnapping": (["kidnap", "kidnapped", "hostage", "confinement", "ransom"],
                   [("Section 359 IPC", "https://indiankanoon.org/doc/10870023/"),
                    ("Section 363 IPC", "https://indiankanoon.org/doc/1131848/")]),
    "extortion": (["blackmail", ""],
                  [("Section 383 IPC", "https://indiankanoon.org/doc/87004389/"),
                   ("Section 384 IPC", "https://indiankanoon.org/doc/23356863/")]),
    "criminal intimidation": ([],
                             [("Section 503 IPC", "https://indiankanoon.org/doc/135084429/"),
                              ("Section 506 IPC", "https://indiankanoon.org/doc/42779199/")]),
    "dacoity": ([],
                [("Section 395 IPC", "https://indiankanoon.org/doc/174974183/")]),
    "drug offenses": ([],
                     [("Section 20 NDPS Act", "https://indiankanoon.org/doc/151794237/"),
                      ("Section 21 NDPS Act", "https://indiankanoon.org/doc/191237800/")]),
    "domestic violence": ([],
                         [("Section 498A IPC", "https://indiankanoon.org/doc/43770801/")]),
    "cybercrime": ([],
                   [("Section 292 IPC", "https://indiankanoon.org/doc/153597150/"),
                    ("Section 67 IT Act", "https://indiankanoon.org/doc/153597150/")]),
    "grievous hurt": ([],
                     [("Section 320 IPC", "https://indiankanoon.org/doc/194159359/"),
                      ("Section 325 IPC", "https://indiankanoon.org/doc/194159359/")]),
    "public nuisance": ([],
                       [("Section 268 IPC", "https://indiankanoon.org/doc/173213527/"),
                        ("Section 290 IPC", "https://indiankanoon.org/doc/90056944/")]),
    "arson": (["fire"],
              [("Section 435 IPC", "https://indiankanoon.org/doc/100471243/"),
               ("Section 436 IPC", None)]),
    "forgery": ([],
                [("Section 463 IPC", None),
                 ("Section 465 IPC", None)]),
    "criminal conspiracy": ([],
                           [("Section 120A IPC", None),
                            ("Section 120B IPC", None)]),
    "rioting": ([],
                [("Section 146 IPC", None),
                 ("Section 147 IPC", None)]),
    "trespass": ([],
                 [("Section 441 IPC", None),
                  ("Section 447 IPC", None)]),
}

stop_words = {"to", "for", "and", "a", "an", "the", "in", "on", "of", "with", "by", "from"}

# Function to suggest sections based on complaint keywords
def suggest_sections(incident_desc):
    incident_desc = incident_desc.lower()
    found_sections = defaultdict(set)
    words_in_complaint = set(re.findall(r'\b\w+\b', incident_desc))
    filtered_words = words_in_complaint - stop_words

    for keyword, (variations, sections) in legal_db.items():
        # Check if any part of the keyword is in filtered words
        if any(part in filtered_words for part in keyword.split()):
            found_sections[keyword].update(sections)
        else:
            # Check variations
            if any(variation in filtered_words for variation in variations):
                found_sections[keyword].update(sections)

    if not found_sections:
        return {"error": "No relevant sections found. Please revise the description or add more details."}

    return {keyword: list(sections) for keyword, sections in found_sections.items()}

# Route to serve the HTML page
@app.route('/')
def home():
    return render_template('frontend1.html')

# Route to handle complaint submission
@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    complaint = data.get('complaint', '')
    relevant_sections = suggest_sections(complaint)
    return jsonify({'relevant_sections': relevant_sections})

# Route to handle voice input
@app.route('/transcribe', methods=['POST'])
def transcribe():
    recognizer = sr.Recognizer()
    audio_file = request.files['audio']
    with sr.AudioFile(audio_file) as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data)
            return jsonify({'transcription': text})
        except sr.UnknownValueError:
            return jsonify({'error': 'Unable to recognize speech'}), 400
        except sr.RequestError as e:
            return jsonify({'error': f'Service unavailable: {e}'}), 503

if __name__ == '__main__':
    app.run(debug=True)
