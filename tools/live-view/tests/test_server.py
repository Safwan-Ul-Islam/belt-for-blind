"""Run with ~/.platformio/penv/bin/python tools/live-view/tests/test_server.py."""
import importlib.util
import json
from pathlib import Path
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("belt_server", HERE / "server.py")
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)


class LiveViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = server_module.LiveState()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), server_module.make_handler(cls.state))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def get(self, path):
        return urlopen(self.url + path, timeout=3)

    def test_home_is_the_3d_workspace_and_dashboard_moved(self):
        with self.get("/") as response:
            self.assertEqual(response.read(), (HERE / "3d.html").read_bytes())
        with self.get("/dashboard") as response:
            self.assertEqual(response.read(), (HERE / "index.html").read_bytes())

    def test_separate_page_and_local_dependencies(self):
        for path, mime in (
            ("/3d", "text/html"), ("/3d/", "text/html"), ("/3d.html", "text/html"),
            ("/3d?view=live", "text/html"), ("/3d.js", "text/javascript"),
            ("/orientation.js", "text/javascript"), ("/live-state.js", "text/javascript"),
            ("/3d.css", "text/css"), ("/assets/scene.json", "application/json"),
            ("/wiring.js", "text/javascript"), ("/wiring.svg", "image/svg+xml"),
            ("/vendor/three/three.module.min.js", "text/javascript"),
            ("/vendor/three/three.core.min.js", "text/javascript"),
            ("/vendor/three/addons/loaders/GLTFLoader.js", "text/javascript"),
            ("/vendor/three/addons/loaders/HDRLoader.js", "text/javascript"),
            ("/vendor/three/addons/utils/BufferGeometryUtils.js", "text/javascript"),
            ("/vendor/three/addons/controls/OrbitControls.js", "text/javascript"),
        ):
            with self.subTest(path=path), self.get(path) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), mime)
                self.assertTrue(response.read())

    def test_real_model_is_binary_gltf(self):
        with self.get("/assets/belt_for_blind.glb") as response:
            self.assertEqual(response.read(4), b"glTF")

    def test_missing_assets_and_traversal_return_404(self):
        for path in ("/assets/missing.glb", "/server.py", "/assets/%2e%2e/server.py", "/vendor/%2e%2e/%2e%2e/server.py"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.get(path)
            self.assertEqual(error.exception.code, 404)

    def test_same_event_stream_carries_imu_gravity_to_both_viewers(self):
        fields = server_module.parse_line("  IMU     tilt  30 deg   motion 0.012 g   gravity  0.50 0.00 0.87", {})
        self.state.update(connected=True, **fields)
        with self.get("/events") as response:
            self.assertEqual(response.headers.get_content_type(), "text/event-stream")
            event = response.readline().decode()
            snapshot = json.loads(event.removeprefix("data: "))
            self.assertEqual(snapshot["imu"]["gravity"], [.5, 0, .87])
            self.assertEqual(snapshot["imu"]["tilt"], 30)
            self.assertTrue(snapshot["connected"])


if __name__ == "__main__":
    unittest.main()
