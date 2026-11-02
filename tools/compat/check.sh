#!/bin/bash
# Проверка совместимости Naby с ОС: установка официальным установщиком, импорт модулей, запуск окна на виртуальном дисплее.
# Запускается внутри контейнера с нужной ОС. Результат — /w/out/<имя>.json и лог /w/out/<имя>.log.
set -u
TAG="${1:-os}"; OUT=/w/out; mkdir -p "$OUT"; LOG="$OUT/$TAG.log"; exec > >(tee -a "$LOG") 2>&1
step(){ echo; echo "=== $*"; }
R=(); ok(){ R+=("\"$1\": \"ok\""); echo "[ok] $1"; }; bad(){ R+=("\"$1\": \"fail: $2\""); echo "[FAIL] $1: $2"; }
. /etc/os-release 2>/dev/null || true
step "ОС: ${PRETTY_NAME:-unknown}"; uname -a
step "пакеты для проверки"
if command -v apt-get >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  timeout 300 apt-get update -qq >/dev/null 2>&1 || true
  if grep -qi "^ID=altlinux" /etc/os-release 2>/dev/null; then   # ALT: apt-rpm, имена пакетов как в RPM
    # зеркало Яндекса быстрее ftp.altlinux.org из облака; списки пакетов должны скачаться целиком (иначе «Broken packages»)
    rm -f /etc/apt/sources.list.d/*.list
    printf 'rpm [p11] http://mirror.yandex.ru/altlinux p11/branch/x86_64 classic\nrpm [p11] http://mirror.yandex.ru/altlinux p11/branch/noarch classic\n' > /etc/apt/sources.list.d/yandex.list
    timeout 900 apt-get update 2>&1 | tail -6
    # базовый образ ALT отстаёт от ветки p11 — без dist-upgrade зависимости «Broken packages»
    timeout 1200 apt-get dist-upgrade -y >/tmp/apt.upgrade.log 2>&1 && echo "+ dist-upgrade" || { echo "- dist-upgrade:"; tail -4 /tmp/apt.upgrade.log | sed 's/^/    /'; }
    for pk in curl tar unzip ca-certificates ca-trust xorg-xvfb xvfb-run xauth libX11 libXext libXrender libXft fontconfig procps; do
      if timeout 300 apt-get install -y "$pk" >/tmp/apt.$pk.log 2>&1; then echo "+ $pk"; else echo "- $pk:"; tail -4 /tmp/apt.$pk.log | sed 's/^/    /'; fi
    done
  else
    timeout 600 apt-get install -y -qq curl tar unzip ca-certificates xvfb xauth libx11-6 libxext6 libxrender1 libxft2 fontconfig procps >/dev/null 2>&1 || true
    timeout 600 apt-get install -y -qq chromium >/dev/null 2>&1 || timeout 600 apt-get install -y -qq chromium-browser >/dev/null 2>&1 || echo "(chromium не поставлен — окно проверяется в Tk)"
  fi
elif command -v dnf >/dev/null; then
  dnf install -y -q curl tar unzip ca-certificates xorg-x11-server-Xvfb xorg-x11-xauth libX11 libXext libXrender libXft fontconfig procps-ng >/dev/null 2>&1 || true
  dnf install -y -q chromium >/dev/null 2>&1 || echo "(chromium не поставлен — окно проверяется в Tk)"
elif command -v yum >/dev/null; then
  yum install -y -q curl tar unzip ca-certificates xorg-x11-server-Xvfb xorg-x11-xauth libX11 libXext libXrender libXft fontconfig procps-ng >/dev/null 2>&1 || true
fi
if ! command -v xvfb-run >/dev/null && command -v Xvfb >/dev/null; then   # нет обёртки xvfb-run — простая замена
  cat > /usr/local/bin/xvfb-run <<'XR'
#!/bin/bash
SCR="-screen 0 1280x800x24"; while [ $# -gt 0 ]; do case "$1" in -a) shift;; -s) SCR="$2"; shift 2;; *) break;; esac; done
Xvfb :99 $SCR >/dev/null 2>&1 & XP=$!; sleep 1; DISPLAY=:99 "$@"; RC=$?; kill $XP 2>/dev/null; exit $RC
XR
  chmod +x /usr/local/bin/xvfb-run
fi
for t in curl tar Xvfb xvfb-run; do command -v $t >/dev/null && ok "tool_$t" || bad "tool_$t" "не найден"; done
step "скачивание установщика с сайта правообладателя"
cd /tmp && curl -fsSL --retry 3 "https://neuralaibaby.tech/naby/dl.php?f=linux" -o Naby_Install_Linux.sh && ok "download" || bad "download" "curl"
ls -la Naby_Install_Linux.sh
step "установка (NABY_NO_START=1)"
export HOME=/root; export NABY_NO_START=1
if bash Naby_Install_Linux.sh; then ok "install"; else bad "install" "код $?"; fi
cd "$HOME/NABY" 2>/dev/null || cd "$HOME"/NABY* 2>/dev/null || { bad "install_dir" "нет ~/NABY"; }
PY="$(ls -d "$PWD"/_skill_environments/app-3.12.*/bin/python 2>/dev/null | head -1)"
echo "python: $PY"; [ -n "$PY" ] && "$PY" -c "import sys,platform;print(sys.version);print(platform.platform())" && ok "python" || bad "python" "нет встроенного Python"
step "версия и целостность"
[ -n "$PY" ] && "$PY" -c "import version;print(version.line())" && ok "version" || bad "version" "import"
[ -n "$PY" ] && "$PY" -c "import core;print('core files', len(core.CORE_FILES))" && ok "core" || bad "core" "import"
step "импорт модулей оболочки"
[ -n "$PY" ] && "$PY" - <<'PYEOF' && ok "imports" || bad "imports" "см. лог"
import importlib, sys
mods = ["version","core","laws","guard","network_policy","updater","profession_packages","professions","tools_catalog","model_pick","ai_connect","attention","rule_state","watchers","kb","brainzone","localbrain","engine","keys","providers","webui"]
bad = []
for m in mods:
    try: importlib.import_module(m)
    except Exception as e: bad.append(f"{m}: {e!r}")
print("imported", len(mods)-len(bad), "of", len(mods)); print("\n".join(bad)); sys.exit(1 if bad else 0)
PYEOF
step "tkinter и виртуальный дисплей"
[ -n "$PY" ] && xvfb-run -a "$PY" -c "import tkinter as tk; r=tk.Tk(); r.update(); print('tk', tk.TkVersion); r.destroy()" && ok "tkinter" || bad "tkinter" "нет Tk/Xvfb"
step "пакеты профессий без сети"
[ -n "$PY" ] && "$PY" - <<'PYEOF' && ok "profession_packages" || bad "profession_packages" "см. лог"
import profession_packages as pp
print("packages:", len(pp.PACKAGES))
svc = pp.service("physicist"); print("physicist functions:", len(getattr(svc, "FUNCTIONS", []) or []))
PYEOF
step "запуск программы на виртуальном дисплее (25 с)"
if [ -n "$PY" ]; then
  rm -f log.txt start_error.txt
  PYTHONUTF8=1 xvfb-run -a -s "-screen 0 1280x800x24" "$PY" -X utf8 neuro_chat.py >"$OUT/$TAG.app.out" 2>&1 &
  APP=$!; sleep 25
  if kill -0 $APP 2>/dev/null; then ok "app_running_25s"; else bad "app_running_25s" "процесс завершился"; fi
  if [ -f start_error.txt ]; then bad "start_error" "$(head -c 200 start_error.txt)"; else ok "start_error"; fi
  # значок в трее: на виртуальном дисплее нет системного трея — сообщение pystray «Failed to dock icon» ожидаемо и не считается ошибкой
  if cat "$OUT/$TAG.app.out" log.txt 2>/dev/null | awk '
      /^Traceback/ {intb=1; tb=""; next}
      intb && /^[ \t]/ {tb=tb $0 "\n"; next}
      intb {intb=0; if (tb !~ /pystray/) {print "REAL TRACEBACK:\n" tb $0; found=1}; next}
      /Error:/ && !/pystray|dock/ {print "ERROR LINE: " $0; found=1}
      END {exit !found}'; then bad "no_traceback" "см. лог"; else ok "no_traceback"; fi
  grep -q "Failed to dock" "$OUT/$TAG.app.out" 2>/dev/null && echo "(трей недоступен на виртуальном дисплее — ожидаемо)"
  echo "--- log.txt (хвост) ---"; tail -n 20 log.txt 2>/dev/null; echo "--- stdout (хвост) ---"; tail -n 20 "$OUT/$TAG.app.out"
  kill $APP 2>/dev/null; sleep 1; kill -9 $APP 2>/dev/null || true
fi
step "итог"
printf '{"os": "%s", "kernel": "%s", "date": "%s", "python": "%s", "results": {%s}}\n' "${PRETTY_NAME:-unknown}" "$(uname -r)" "$(date -u +%FT%TZ)" "$([ -n "$PY" ] && "$PY" -c 'import sys;print(sys.version.split()[0])')" "$(IFS=,; echo "${R[*]}")" | tee "$OUT/$TAG.json"
sync; ls -la "$OUT"
case " ${R[*]} " in *fail:*) exit 1;; *) exit 0;; esac
