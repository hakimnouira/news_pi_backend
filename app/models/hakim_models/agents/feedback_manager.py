import json

class FeedbackManager:
    def __init__(self, filename="rlhf_feedback.jsonl"):
        self.filename = filename
        self.feedback_log = []

    def add_feedback(self, prompt, chosen, rejected, notes=""):
        self.feedback_log.append({
            "prompt": prompt,
            "chosen": chosen,
            "rejected": rejected,
            "notes": notes
        })

    def dump_to_file(self):
        # Dump as JSONL (one JSON object per line)
        with open(self.filename, "w") as f:
            for entry in self.feedback_log:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
