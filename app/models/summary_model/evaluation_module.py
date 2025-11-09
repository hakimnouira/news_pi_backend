"""
Module d'évaluation complet des summarizers avec ROUGE, BERTScore et génération de rapport.
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import numpy as np
import spacy
from sentence_transformers import SentenceTransformer, util

from rouge_score import rouge_scorer
import bert_score

logging.basicConfig(level=logging.INFO)


class SummarizerEvaluator:
    """Évalue et compare les performances des différentes méthodes de résumé."""

    def __init__(self):
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            self.nlp = None
            logging.warning("spaCy model not loaded - certaines métriques indisponibles")

    def evaluate_single_summary(
        self,
        original_text: str,
        summary: Dict,
        method_name: str,
        reference_summary: Optional[str] = None
    ) -> Dict:
        """Évalue un résumé, avec ROUGE & BERTScore si référence fournie."""

        metrics = {
            "method": method_name,
            "timestamp": datetime.now().isoformat(),
        }

        # 1. Similarité sémantique
        try:
            orig_emb = self.embedding_model.encode(original_text[:3000])
            summ_emb = self.embedding_model.encode(summary['summary'])
            metrics['semantic_similarity'] = float(util.cos_sim(orig_emb, summ_emb).item())
        except:
            metrics['semantic_similarity'] = 0.0

        # 2. Couverture des entités
        if self.nlp and summary.get('entities'):
            try:
                orig_doc = self.nlp(original_text[:5000])
                orig_entities = set([ent.text.lower() for ent in orig_doc.ents
                                     if ent.label_ in ['PERSON', 'ORG', 'GPE', 'EVENT']])
                summ_entities = set()
                for lst in summary['entities'].values():
                    summ_entities.update([e.lower() for e in lst])
                metrics['entity_coverage'] = len(orig_entities & summ_entities) / len(orig_entities) if orig_entities else 0.0
            except:
                metrics['entity_coverage'] = 0.0
        else:
            metrics['entity_coverage'] = 0.0

        # 3. Concision
        orig_words = len(original_text.split())
        summ_words = len(summary['summary'].split())
        metrics['compression_ratio'] = summ_words / orig_words if orig_words else 0
        metrics['absolute_length'] = summ_words

        # 4. Qualité du titre
        title = summary.get('title', '')
        metrics['title_length'] = len(title.split())
        metrics['title_quality_score'] = self._evaluate_title_quality(title, summary['summary'])

        # 5. Structure 5W1H
        structure = summary.get('structure_5w1h', {})
        metrics['structure_completeness'] = sum(1 for v in structure.values() if v) / 6

        # 6. Citations
        quotes = summary.get('key_quotes', [])
        metrics['num_quotes'] = len(quotes)
        metrics['avg_quote_length'] = np.mean([len(q.split()) for q in quotes]) if quotes else 0

        # 7. Factualité
        has_numbers = bool(summary.get('numbers_events', {}).get('numbers'))
        has_date = summary.get('date_published') != "Not specified"
        metrics['factuality_score'] = (has_numbers + has_date) / 2

        # 8. Temps de traitement
        metadata = summary.get('metadata', {})
        metrics['processing_time'] = metadata.get('processing_time', 0)

        # 9. Score global
        metrics['overall_score'] = self._calculate_overall_score(metrics)

        # 10. ROUGE & BERTScore
        if reference_summary:
            try:
                scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
                rouge_scores = scorer.score(reference_summary, summary['summary'])
                metrics['rouge1'] = rouge_scores['rouge1'].fmeasure
                metrics['rouge2'] = rouge_scores['rouge2'].fmeasure
                metrics['rougeL'] = rouge_scores['rougeL'].fmeasure
            except:
                metrics['rouge1'] = metrics['rouge2'] = metrics['rougeL'] = 0.0

            try:
                P, R, F1 = bert_score.score([summary['summary']], [reference_summary],
                                            lang='en', rescale_with_baseline=True)
                metrics['bertscore_f1'] = F1.mean().item()
            except:
                metrics['bertscore_f1'] = 0.0

        return metrics

    def _evaluate_title_quality(self, title: str, summary: str) -> float:
        score = 0.0
        words = len(title.split())
        if 5 <= words <= 12:
            score += 0.4
        elif 3 <= words <= 15:
            score += 0.2
        if title.lower() not in ["news summary", "article summary", "summary", "news"]:
            score += 0.3
        try:
            emb_title = self.embedding_model.encode(title)
            emb_sum = self.embedding_model.encode(summary[:500])
            score += 0.3 * float(util.cos_sim(emb_title, emb_sum).item())
        except:
            pass
        return min(score, 1.0)

    def _calculate_overall_score(self, metrics: Dict) -> float:
        weights = {
            'semantic_similarity': 0.30,
            'entity_coverage': 0.20,
            'title_quality_score': 0.15,
            'structure_completeness': 0.15,
            'factuality_score': 0.10
        }
        base = sum(metrics.get(k, 0) * w for k, w in weights.items())
        comp = metrics.get('compression_ratio', 0)
        bonus = 0.10 if 0.15 <= comp <= 0.35 else 0.05 if 0.10 <= comp <= 0.45 else 0
        return min(base + bonus, 1.0)

    def compare_methods(
        self,
        original_text: str,
        results: Dict[str, Dict],
        reference_summary: Optional[str] = None
    ) -> Dict:
        comparisons = {}
        for method, summary in results.items():
            if summary:
                comparisons[method] = self.evaluate_single_summary(original_text, summary, method, reference_summary)
        ranked = sorted(comparisons.items(), key=lambda x: x[1]['overall_score'], reverse=True)
        return {
            "detailed_metrics": comparisons,
            "ranking": [
                {"rank": i + 1, "method": m, "overall_score": metrics['overall_score'],
                 "processing_time": metrics['processing_time']}
                for i, (m, metrics) in enumerate(ranked)
            ],
            "best_method": ranked[0][0] if ranked else None
        }

    def generate_report(self, comparison: Dict, output_file="evaluation_report.txt") -> str:
        """Génère un rapport texte complet avec toutes les métriques."""
        report = ["="*80, "RAPPORT D'ÉVALUATION DES MÉTHODES DE RÉSUMÉ", "="*80]
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        report.append("="*80)
        report.append(" CLASSEMENT GÉNÉRAL")
        report.append("="*80)
        for r in comparison['ranking']:
            report.append(f"{r['rank']}. {r['method'].upper()} - Score global: {r['overall_score']:.3f}, "
                          f"Temps: {r['processing_time']:.2f}s")

        report.append("\n" + "="*80)
        report.append(" MÉTRIQUES DÉTAILLÉES")
        report.append("="*80)
        for method, metrics in comparison['detailed_metrics'].items():
            report.append(f"\n{method.upper()}")
            report.append(f"  Similarité sémantique: {metrics['semantic_similarity']:.3f}")
            report.append(f"  Couverture entités: {metrics['entity_coverage']:.3f}")
            report.append(f"  Complétude 5W1H: {metrics['structure_completeness']:.3f}")
            report.append(f"  Score factualité: {metrics['factuality_score']:.3f}")
            report.append(f"  Score titre: {metrics['title_quality_score']:.3f} ({metrics['title_length']} mots)")
            report.append(f"  Ratio compression: {metrics['compression_ratio']:.3f}, Longueur résumé: {metrics['absolute_length']}")
            report.append(f"  Citations: {metrics['num_quotes']}, Longueur moy.: {metrics['avg_quote_length']:.1f} mots")
            if 'rouge1' in metrics:
                report.append(f"  ROUGE-1: {metrics['rouge1']:.3f}, ROUGE-2: {metrics['rouge2']:.3f}, ROUGE-L: {metrics['rougeL']:.3f}")
            if 'bertscore_f1' in metrics:
                report.append(f"  BERTScore F1: {metrics['bertscore_f1']:.3f}")

        report.append("\n" + "="*80)
        report.append(f"Meilleure méthode: {comparison['best_method'].upper()}")
        report_text = "\n".join(report)

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            logging.info(f"Rapport sauvegardé: {output_file}")
        except Exception as e:
            logging.error(f"Erreur sauvegarde rapport: {e}")

        return report_text


if __name__ == "__main__":
    print(">>> Test complet du module d'évaluation avec ROUGE & BERTScore")

    evaluator = SummarizerEvaluator()

    test_results = {
        "bart": {
            "title": "Tech Giant Announces AI Breakthrough",
            "summary": "TechCorp unveiled revolutionary AI system...",
            "entities": {"PERSON": ["John"], "ORG": ["TechCorp"]},
            "structure_5w1h": {"Who": ["TechCorp"], "What": ["announced"]},
            "key_quotes": ["This is revolutionary"],
            "numbers_events": {"numbers": ["$2B"]},
            "date_published": "October 23, 2025",
            "metadata": {"processing_time": 2.5}
        },
        "llama": {
            "title": "AI Innovation by TechCorp",
            "summary": "TechCorp introduced a new AI technology...",
            "entities": {"PERSON": ["John"], "ORG": ["TechCorp"]},
            "structure_5w1h": {"Who": ["TechCorp"], "What": ["introduced"]},
            "key_quotes": ["AI will change everything"],
            "numbers_events": {"numbers": ["$2B"]},
            "date_published": "October 23, 2025",
            "metadata": {"processing_time": 3.1}
        }
    }

    test_text = "TechCorp announced a revolutionary AI system today..."
    reference_summary = "TechCorp has unveiled a revolutionary AI system today that will change the tech industry."

    comparison = evaluator.compare_methods(test_text, test_results, reference_summary)
    report = evaluator.generate_report(comparison)

    print("\n✅ Rapport généré !\n")
    print(report)
