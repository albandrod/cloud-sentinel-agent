
import unittest
from unittest.mock import patch, MagicMock
from agents.writer import writer_node
from schema.state import AgentState

class TestWriterNodeReportType(unittest.TestCase):
    @patch("agents.writer.AzureChatOpenAI")
    @patch("agents.writer.ChatPromptTemplate")
    def test_ambiguous_prompt_technical_executive(self, mock_prompt, mock_llm):
        # Mock LLM chain to return a fake response
        fake_chain = MagicMock()
        fake_chain.invoke.return_value.content = "### [NUBE] - Nueva función\nContexto: ..."
        mock_prompt.from_messages.return_value.__or__.return_value = fake_chain
        mock_llm.return_value = MagicMock()

        state = AgentState()
        state["analyzed_news"] = [{"source": "azure", "title": "Nueva función"}]
        state["user_instructions"] = "Genera un informe técnico ejecutivo de Azure"
        state["lang"] = "es"
        state["report_type"] = "técnico ejecutivo"
        result = writer_node(state)
        # The report is written to file, but also check the returned dict if present
        # Accept either label, or check for both words in the markdown file
        # For test, just check the file was written and content includes expected label
        import datetime
        tipo_label_file = "técnico ejecutivo".lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
        fecha_hoy = str(datetime.date.today())
        filename = f"reports/informe_{tipo_label_file}_{fecha_hoy}.md"
        with open(filename, encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Informe Técnico Multi-Cloud", content)
            self.assertTrue("Técnico" in content or "Ejecutivo" in content)

    @patch("agents.writer.AzureChatOpenAI")
    @patch("agents.writer.ChatPromptTemplate")
    def test_mixed_prompt_custom(self, mock_prompt, mock_llm):
        fake_chain = MagicMock()
        fake_chain.invoke.return_value.content = "### [NUBE] - Nueva alerta\nContexto: ..."
        mock_prompt.from_messages.return_value.__or__.return_value = fake_chain
        mock_llm.return_value = MagicMock()

        state = AgentState()
        state["analyzed_news"] = [{"source": "aws", "title": "Nueva alerta"}]
        state["user_instructions"] = "Informe personalizado ejecutivo de AWS"
        state["lang"] = "es"
        state["report_type"] = "personalizado ejecutivo"
        result = writer_node(state)
        import datetime
        tipo_label_file = "personalizado ejecutivo".lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
        fecha_hoy = str(datetime.date.today())
        filename = f"reports/informe_{tipo_label_file}_{fecha_hoy}.md"
        with open(filename, encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Informe Personalizado Multi-Cloud", content)

if __name__ == "__main__":
    unittest.main()
