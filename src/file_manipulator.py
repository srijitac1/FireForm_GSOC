import os
from datetime import datetime
from pathlib import Path
from src.filler import Filler
from src.llm import LLM
from src.paths import resolve_path, to_relative, OUTPUTS_DIR
from commonforms import prepare_form


class FileManipulator:
    def __init__(self):
        self.filler = Filler()
        self.llm = LLM()

    def create_template(self, pdf_path: str) -> str:
        """
        By using commonforms, we create an editable .pdf template and we store it.
        Returns a relative path string from the project root.
        """
        template_path = pdf_path[:-4] + "_template.pdf"
        prepare_form(pdf_path, template_path)
        # Store relative path so records are stable across machines
        return to_relative(template_path)

    def get_output_path(self, template_path: str) -> str:
        """
        Build the output path for a filled PDF inside OUTPUTS_DIR.
        Pattern: <basename>_<timestamp>_filled.pdf
        Creates OUTPUTS_DIR if it does not exist.
        """
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        basename = Path(template_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return str(OUTPUTS_DIR / f"{basename}_{timestamp}_filled.pdf")

    def fill_form(self, user_input: str, fields: list, pdf_form_path: str):
        """
        Receives raw data, runs the PDF filling logic, and returns the path
        to the newly created file (relative to project root).
        """
        print("[1] Received request from frontend.")
        print(f"[2] PDF template path: {pdf_form_path}")

        # Resolve relative paths to absolute before checking existence
        abs_path = str(resolve_path(pdf_form_path)) if not os.path.isabs(pdf_form_path) else pdf_form_path

        if not os.path.exists(abs_path):
            print(f"Error: PDF template not found at {abs_path}")
            return None

        print("[3] Starting extraction and PDF filling process...")
        try:
            self.llm._target_fields = fields
            self.llm._transcript_text = user_input
            output_path = self.get_output_path(abs_path)
            output_name = self.filler.fill_form(
                pdf_form=abs_path, llm=self.llm, output_path=output_path
            )

            print("\n----------------------------------")
            print("✅ Process Complete.")
            print(f"Output saved to: {output_name}")

            return output_name

        except Exception as e:
            print(f"An error occurred during PDF generation: {e}")
            raise e
