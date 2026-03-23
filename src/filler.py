from pdfrw import PdfReader, PdfWriter
from src.llm import LLM
from datetime import datetime
from typing import Dict, Any


class Filler:
    def __init__(self):
        pass

    def fill_form(self, pdf_form: str, llm: LLM):
        """
        Fill a PDF form with values extracted via LLM.
        Fields are filled in visual order (top-to-bottom, left-to-right).
        """
        output_pdf = (
            pdf_form[:-4]
            + "_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + "_filled.pdf"
        )

        t2j = llm.main_loop()
        textbox_answers = t2j.get_data()

        return self._write_pdf(pdf_form, output_pdf, list(textbox_answers.values()))

    def fill_form_with_data(self, pdf_form: str, data: Dict[str, Any]) -> str:
        """
        Fill a PDF form from a pre-extracted data dictionary.
        Used by the batch endpoint so LLM extraction runs only once for all templates.

        Fields are matched positionally (top-to-bottom, left-to-right) using the
        values from `data` in insertion order — the same deterministic ordering
        used by fill_form().

        Args:
            pdf_form: Path to the fillable PDF template.
            data: Dict mapping field labels to extracted values.

        Returns:
            Path to the filled output PDF.
        """
        output_pdf = (
            pdf_form[:-4]
            + "_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + "_filled.pdf"
        )
        return self._write_pdf(pdf_form, output_pdf, list(data.values()))

    def _write_pdf(self, pdf_form: str, output_pdf: str, answers_list: list) -> str:
        """
        Internal helper: write answers_list into pdf_form and save to output_pdf.
        """
        pdf = PdfReader(pdf_form)

        for page in pdf.pages:
            if page.Annots:
                sorted_annots = sorted(
                    page.Annots, key=lambda a: (-float(a.Rect[1]), float(a.Rect[0]))
                )

                i = 0
                for annot in sorted_annots:
                    if annot.Subtype == "/Widget" and annot.T:
                        if i < len(answers_list):
                            annot.V = f"{answers_list[i]}"
                            annot.AP = None
                            i += 1
                        else:
                            break

        PdfWriter().write(output_pdf, pdf)
        return output_pdf
