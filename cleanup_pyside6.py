import os
import glob
import shutil

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "Lib", "site-packages", "PySide6")
marker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", ".cleaned")

if not os.path.isdir(base):
    print("PySide6 not found, skipping cleanup.")
else:
    for f in glob.glob(os.path.join(base, "resources", "*.debug.*")):
        os.remove(f)

    locales = os.path.join(base, "translations", "qtwebengine_locales")
    for f in glob.glob(os.path.join(locales, "*.pak")):
        if os.path.basename(f) not in ("zh-CN.pak", "en-US.pak"):
            os.remove(f)

    for f in glob.glob(os.path.join(base, "translations", "*.qm")):
        os.remove(f)

    for d in ("qml", "metatypes"):
        p = os.path.join(base, d)
        if os.path.isdir(p):
            shutil.rmtree(p)

    for pat in ("opengl32sw.dll", "avcodec-*.dll", "avformat-*.dll", "avutil-*.dll",
                "Qt6Designer.dll", "Qt6DesignerComponents.dll", "qmlls.exe", "qmlformat.exe"):
        for f in glob.glob(os.path.join(base, pat)):
            os.remove(f)

    open(marker, "w").close()
    print("Cleanup done.")
