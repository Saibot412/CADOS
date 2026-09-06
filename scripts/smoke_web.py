"""Optional real-browser integration check, using only temporary test data."""
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from playwright.sync_api import sync_playwright, expect
from server.app.main import create_app
from cados.config import AppConfig
from cados.services.storage import DataStore
from cados.services.workout_library import WorkoutLibraryClient
from cados.services.account_sync import AccountSync

def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        app=create_app("sqlite:///"+str(root/"test.sqlite3"),"http://127.0.0.1:8765",
            bootstrap=("browser@example.test","browser-password-123"))
        server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=8765,log_level="warning"))
        thread=threading.Thread(target=server.run,daemon=True);thread.start()
        for _ in range(100):
            if server.started:break
            if not thread.is_alive():raise RuntimeError("Testserver konnte nicht starten")
            time.sleep(.05)
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                page=browser.new_page(viewport={"width":1440,"height":1000})
                errors=[];page.on("pageerror",lambda error: errors.append(str(error)))
                page.goto("http://127.0.0.1:8765")
                expect(page.get_by_role("heading",name="Willkommen bei CADOS")).to_be_visible()
                page.screenshot(path="/private/tmp/cados-login.png",full_page=True)
                page.locator('#login-form input[name=email]').fill("browser@example.test")
                page.locator('#login-form input[name=password]').fill("browser-password-123")
                page.get_by_role("button",name="Anmelden",exact=True).click()
                expect(page.locator(".workout-card")).to_have_count(26)
                page.screenshot(path="/private/tmp/cados-workouts.png",full_page=True)
                page.locator('#file').set_input_files({"name":"Browser.zwo","mimeType":"application/xml","buffer":b'<workout_file><name>Browser Test</name><workout><SteadyState Duration="60" Power="0.8"/></workout></workout_file>'})
                expect(page.locator(".workout-card")).to_have_count(27)
                page.get_by_role("searchbox").fill("Browser Test")
                expect(page.locator(".workout-card")).to_have_count(1)
                page.get_by_role("button",name="Ansehen & bearbeiten").click()
                page.locator('#edit-form input[name=name]').fill("Browser Edited")
                page.locator('#save-edit').click()
                expect(page.locator('#editor')).not_to_be_visible()
                page.get_by_role("searchbox").fill("Browser Edited")
                expect(page.locator(".workout-card")).to_have_count(1)
                page.get_by_role("button",name="Mein Profil",exact=True).click()
                page.get_by_role("button",name="Profil anlegen").click()
                page.locator('#edit-form input[name=name]').fill("Browser Rider")
                page.locator('#edit-form input[name=ftp]').fill("275")
                page.locator('#save-edit').click()
                expect(page.locator('#profiles')).to_contain_text("275 W FTP")
                desktop=WorkoutLibraryClient("http://127.0.0.1:8765", "")
                desktop.login("browser@example.test","browser-password-123")
                store=DataStore(root/"desktop.sqlite3")
                sync=AccountSync(store,desktop,AppConfig.load(root))
                sync.run()
                profile=store.list_profiles()[0]
                assert profile.ftp==275
                profile.ftp=290
                store.save_profile(profile)
                sync.run()
                page.get_by_role("button",name="Aktualisieren",exact=True).click()
                expect(page.locator('#profiles')).to_contain_text("290 W FTP")
                page.set_viewport_size({"width":390,"height":844})
                page.get_by_role("button",name="Workouts",exact=True).click()
                page.screenshot(path="/private/tmp/cados-mobile.png",full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile overflow"
                page.get_by_role("button",name="Abmelden",exact=True).click()
                expect(page.locator('#login')).to_be_visible()
                assert not errors, errors
                browser.close()
                print("Browser smoke passed: login, import, edit, profile, desktop HTTP sync both ways, mobile, logout; no JavaScript errors")
        finally:
            server.should_exit=True;thread.join(timeout=10)

if __name__=="__main__":main()
