"""A deployed app is shared: several users write to one knowledge base at the same time, and each sees the others' documents."""
import os
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [HERE, os.path.join(HERE, "tests")]

from capital_agent.rag_store import RagStore  # noqa: E402
from test_rbi_brain import BASE, pdf_bytes  # noqa: E402


class TestSharedStore(unittest.TestCase):
    def test_concurrent_users_and_visibility(self):
        path = os.path.join(tempfile.mkdtemp(), "rag.sqlite")
        RagStore(path)                                            # create once
        errors, users = [], 6

        def user(i):
            try:
                st = RagStore(path)                               # each session has its own connection
                st.ingest({"id": f"DOC-{i}", "title": f"Directions {i}", "type": "pdf", "framework": "NBFC",
                           "effective_from": "2025-11-28"}, pdf_bytes([f"Document {i}"] + BASE[1:]))
            except Exception as e:                                # 'database is locked' would land here
                errors.append(repr(e))

        threads = [threading.Thread(target=user, args=(i,)) for i in range(users)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        viewer = RagStore(path)                                   # a different user opens the app afterwards
        self.assertEqual({d["doc_id"] for d in viewer.documents()}, {f"DOC-{i}" for i in range(users)})


if __name__ == "__main__":
    unittest.main()
