#!/usr/bin/env python3
"""mutate-batch.py — bin/mutate 的 --batch / --check 實作（Python 3.9 stdlib，無第三方依賴）。

由 `bin/mutate --batch <清單檔> [--check] [--out <目錄>] [--cwd <目錄>]` 轉呼，
不直接對外提供 CLI 入口（入口一律是 `bin/mutate`，且一律用 `bash bin/mutate ...` 呼叫，
不得依賴 PATH 上可能存在的其他 `mutate`）。

清單檔格式見 bin/mutate 檔頭註解。
"""
import filecmp
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

EXIT_OK = 0
EXIT_RESTORE_FAILED = 1
EXIT_FORMAT_ERROR = 2
EXIT_NOT_APPLIED = 3
EXIT_FAIL = 4
EXIT_CONTROL_ABORT = 5
EXIT_COMPILE_RED = 6
EXIT_INTERNAL_ERROR = 7

COMMENT_WARNING = "所有變動行看起來都是註解"


class FormatError(Exception):
    pass


class RestoreFailure(Exception):
    pass


def eprint(*a, **kw):
    print(*a, file=sys.stderr, **kw)
    sys.stderr.flush()


# --------------------------------------------------------------------------
# 參數解析
# --------------------------------------------------------------------------

def parse_args(argv):
    opts = {"batch": None, "check": False, "out": None, "cwd": None}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--batch":
            if i + 1 >= len(argv):
                raise FormatError("--batch 缺值")
            opts["batch"] = argv[i + 1]
            i += 2
        elif a == "--check":
            opts["check"] = True
            i += 1
        elif a == "--out":
            if i + 1 >= len(argv):
                raise FormatError("--out 缺值")
            opts["out"] = argv[i + 1]
            i += 2
        elif a == "--cwd":
            if i + 1 >= len(argv):
                raise FormatError("--cwd 缺值")
            opts["cwd"] = argv[i + 1]
            i += 2
        else:
            raise FormatError("未知參數: %s" % a)
    if not opts["batch"]:
        raise FormatError("--batch <清單檔> 必填")
    return opts


# --------------------------------------------------------------------------
# 清單檔解析
# --------------------------------------------------------------------------

def parse_blocks(text):
    blocks = []
    current = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            # 註解行：視為不存在，不當空行處理（不會意外把兩個區塊斷開，也不會混進 key）
            continue
        if stripped == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)

    parsed = []
    for block in blocks:
        d = {}
        for line in block:
            if ":" not in line:
                raise FormatError("非 key: value 行: %r" % line)
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if not k:
                raise FormatError("空 key: %r" % line)
            if k in d:
                # 同區塊重複 key：多半是漏了一個空行，把兩條變異的欄位擠成一條，
                # 後者會靜默蓋掉前者——寧可硬報格式錯，不要吞掉一條變異。
                raise FormatError("同區塊重複的 key（是不是漏了空行分隔兩條變異）: %s" % k)
            d[k] = v
        parsed.append(d)
    return parsed


GLOBAL_KEYS = {"cwd", "test", "compile"}
ENTRY_KEYS = {"id", "file", "sed", "patch", "test", "compile", "expect"}
ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _native_path(p):
    """PC 版：清單檔裡的 Git Bash 路徑（/c/Users/...、/tmp/...）Windows Python 看不懂，
    用 cygpath 轉成 C:\\...；命令列參數 MSYS 會自動轉，但清單檔內容不會。"""
    if os.name == "nt" and p.startswith("/"):
        try:
            r = subprocess.run(["cygpath", "-w", p], capture_output=True, text=True)
        except FileNotFoundError:  # 不在 Git Bash 裡跑（PATH 無 usr/bin）：原樣交回，後面的存在檢查會報錯
            return p
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return p


def load_mutations(list_path, cli_cwd):
    if not os.path.isfile(list_path):
        raise FormatError("清單檔不存在: %s" % list_path)
    with open(list_path, "r", encoding="utf-8") as f:
        text = f.read()
    blocks = parse_blocks(text)
    if not blocks:
        raise FormatError("清單檔是空的")

    defaults = {}
    if "id" not in blocks[0]:
        defaults = blocks[0]
        mutations = blocks[1:]
    else:
        mutations = blocks

    for k in defaults:
        if k not in GLOBAL_KEYS:
            raise FormatError("全域預設區塊含未知 key（拼錯了嗎）: %s" % k)
    for m in mutations:
        for k in m:
            if k not in ENTRY_KEYS:
                raise FormatError("id=%s 含未知 key（拼錯了嗎）: %s" % (m.get("id", "?"), k))

    if not mutations:
        raise FormatError("清單檔沒有任何變異區塊")

    # cwd 解析：--cwd 覆寫清單檔 cwd:；兩者皆無時用 process cwd
    base_cwd = cli_cwd if cli_cwd else (defaults.get("cwd") or os.getcwd())
    cwd_abs = os.path.abspath(os.path.expanduser(_native_path(base_cwd)))

    entries = []
    seen_ids = set()
    for idx, m in enumerate(mutations):
        eid = m.get("id")
        if not eid:
            raise FormatError("第 %d 條缺 id" % (idx + 1))
        if not ID_RE.match(eid) or ".." in eid:
            raise FormatError("id 格式不合法（僅允許英數字、. _ -，且不得含 ..）: %s" % eid)
        if eid in seen_ids:
            raise FormatError("id 重複: %s" % eid)
        seen_ids.add(eid)

        file_ = m.get("file")
        if not file_:
            raise FormatError("id=%s 缺 file" % eid)

        sed_expr = m.get("sed")
        patch_rel = m.get("patch")
        if bool(sed_expr) == bool(patch_rel):
            raise FormatError("id=%s 的 sed / patch 必須恰給一個" % eid)

        expect = m.get("expect", "red")
        if expect not in ("red", "green"):
            raise FormatError("id=%s expect 必須是 red 或 green" % eid)

        test_cmd = m.get("test") or defaults.get("test")
        if not test_cmd:
            raise FormatError("id=%s 缺 test（本條與全域都沒有）" % eid)

        compile_cmd = m.get("compile") or defaults.get("compile") or ""

        target = os.path.join(cwd_abs, _native_path(file_))
        if not os.path.isfile(target):
            raise FormatError("id=%s 目標檔不存在: %s" % (eid, target))

        patch_path = None
        if patch_rel:
            patch_path = os.path.join(cwd_abs, _native_path(patch_rel))
            if not os.path.isfile(patch_path):
                raise FormatError("id=%s patch 檔不存在: %s" % (eid, patch_path))

        entries.append({
            "id": eid,
            "file": file_,
            "target": target,
            "sed": sed_expr,
            "patch": patch_path,
            "test": test_cmd,
            "compile": compile_cmd,
            "expect": expect,
        })

    if entries[0]["id"] != "control":
        raise FormatError("第一條必須是控制組（id: control）")
    if entries[0]["expect"] != "red":
        raise FormatError("控制組（第一條）expect 必須是 red")

    return cwd_abs, entries


# --------------------------------------------------------------------------
# 單條執行
# --------------------------------------------------------------------------

def _install_signal_handlers():
    def _to_interrupt(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGINT, _to_interrupt)
    signal.signal(signal.SIGTERM, _to_interrupt)


def _looks_comment_only(diff_text):
    # 判準與 bin/mutate 檔身（單條模式）那份是兩份獨立維護的複本，改這裡記得同步改那邊。
    changed = [l for l in diff_text.splitlines()
               if (l.startswith("+") or l.startswith("-"))
               and not l.startswith("+++") and not l.startswith("---")]
    if not changed:
        return False
    non_comment = [l for l in changed if not re.match(r"^[+-]\s*(//|#|\*|/\*)", l)]
    return len(non_comment) == 0


def _find_bash():
    """PC 版：Windows 的 CreateProcess 與 PowerShell 的 PATH 都可能先找到 System32 的 bash.exe
    （WSL stub），必須用 Git Bash。找不到就明確報錯，不讓測試靜默跑在 WSL stub 上。"""
    b = shutil.which("bash")
    if os.name != "nt":
        return b or "bash"
    if b and "system32" not in b.lower():
        return b
    git = shutil.which("git")  # ...\Git\cmd\git.exe → ...\Git\bin\bash.exe
    if git:
        cand = os.path.join(os.path.dirname(os.path.dirname(git)), "bin", "bash.exe")
        if os.path.isfile(cand):
            return cand
    sys.exit("[錯誤] 找不到 Git Bash（只找到 WSL stub）。請從 Git Bash 執行 bin/mutate。")


def _has_gnu_sed():
    try:
        return subprocess.run(["sed", "--version"], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


BASH = _find_bash()
GNU_SED = _has_gnu_sed()


def _kill_group(p, sig):
    if os.name == "nt":
        # Windows 沒有 killpg：taskkill /T 連子孫一起收（/F 即 SIGKILL 等級）
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        return
    try:
        os.killpg(os.getpgid(p.pid), sig)
    except ProcessLookupError:
        pass


def _run_group(cmd, cwd):
    """跑一句 shell 指令字串：用 bash -c（不是 /bin/sh，才吃得下 <(...) 這類 bash 語法，
    與單條模式的 `eval "$TEST_CMD"` 對齊）；起自己的 process group（start_new_session），
    中斷（KeyboardInterrupt）時呼叫端可對整個 group 送信號，孫行程（sleep/go test）
    不會變孤兒。回傳 (returncode, stdout, stderr)。"""
    with subprocess.Popen([BASH, "-c", cmd], cwd=cwd, start_new_session=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as p:
        try:
            out, err = p.communicate()
        except KeyboardInterrupt:
            _kill_group(p, signal.SIGTERM)
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 測試指令自己擋掉了 SIGTERM（例如 trap '' TERM）：SIGTERM 殺不動就
                # 升級 SIGKILL，不然孫行程會變孤兒一直跑下去。
                _kill_group(p, getattr(signal, "SIGKILL", signal.SIGTERM))
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            raise
        return p.returncode, out, err


def run_entry(entry, cwd_abs, out_dir, check_mode):
    target = entry["target"]
    fd, backup_path = tempfile.mkstemp(prefix="mutate-batch-")
    os.close(fd)
    shutil.copyfile(target, backup_path)

    log = []
    log.append("=== id: %s ===" % entry["id"])
    log.append("file: %s" % entry["file"])

    applied = False
    compile_col = "-"
    test_col = "-"
    verdict = None
    t0 = time.time()
    try:
        patch_failed = False
        sed_failed = False
        if entry["sed"]:
            r = subprocess.run(["sed", "-i"] + ([] if GNU_SED else [""]) + ["-e", entry["sed"], target],
                                capture_output=True, text=True)
            log.append("--- sed ---\n%s" % (r.stderr or ""))
            if r.returncode != 0:
                sed_failed = True
                sed_fail_msg = "[變異] !! sed 執行失敗（exit %d）：%s" % (r.returncode, (r.stderr or "").strip())
                log.append(sed_fail_msg)
                eprint(sed_fail_msg)
        else:
            with open(entry["patch"], "rb") as pf:
                r = subprocess.run(["patch", "-p0", "--no-backup-if-mismatch", target],
                                    cwd=cwd_abs, stdin=pf, capture_output=True, text=True)
            log.append("--- patch ---\n%s%s" % (r.stdout or "", r.stderr or ""))
            patch_failed = (r.returncode != 0)

        diff_proc = subprocess.run(["diff", "-u", backup_path, target],
                                    capture_output=True, text=True)
        diff_text = diff_proc.stdout
        log.append("--- diff（空＝變異沒套上）---\n%s" % diff_text)

        if patch_failed or sed_failed or diff_text.strip() == "":
            applied = False
            verdict = "not-applied"
            log.append("[變異] !! 沒套上（sed/patch 失敗或 diff 為空）。")
        else:
            applied = True
            if _looks_comment_only(diff_text):
                warn = "[變異] !! 警告：%s——疑似只換到註解的假陰性。" % COMMENT_WARNING
                log.append(warn)
                eprint(warn)

            if not check_mode:
                if entry["compile"]:
                    c_rc, c_out, c_err = _run_group(entry["compile"], cwd_abs)
                    log.append("--- compile: %s ---\n%s%s" %
                               (entry["compile"], c_out or "", c_err or ""))
                    if c_rc != 0:
                        compile_col = "red"
                        verdict = "compile-red"
                    else:
                        compile_col = "ok"

                if verdict != "compile-red":
                    t_rc, t_out, t_err = _run_group(entry["test"], cwd_abs)
                    log.append("--- test: %s ---\n%s%s" %
                               (entry["test"], t_out or "", t_err or ""))
                    test_col = "red" if t_rc != 0 else "green"
                    verdict = "PASS" if test_col == entry["expect"] else "FAIL"
    finally:
        restore_err = None
        try:
            shutil.copyfile(backup_path, target)
        except OSError as e:
            restore_err = str(e)
        same = (restore_err is None) and filecmp.cmp(backup_path, target, shallow=False)

        # patch 失敗／成功都可能留下 .rej / .orig，還原後一併清掉
        for suffix in (".rej", ".orig"):
            p = target + suffix
            if os.path.isfile(p):
                os.remove(p)

        if not same:
            msg = ("id=%s 還原失敗：%s；備份留在 %s" %
                   (entry["id"], restore_err or "cmp 後與備份不一致", backup_path))
            log.append("[還原] !! %s" % msg)
            if out_dir:
                _write_log(out_dir, entry["id"], log)
            raise RestoreFailure(msg)

        log.append("[還原] OK：逐位一致")
        os.remove(backup_path)

    elapsed = int(round(time.time() - t0))
    if out_dir:
        _write_log(out_dir, entry["id"], log)
    return applied, compile_col, test_col, verdict, elapsed


def _write_log(out_dir, entry_id, log_lines):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "%s.log" % entry_id), "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def default_out_dir(list_path):
    return os.path.join(os.path.dirname(os.path.abspath(list_path)), "mutate-out")


def main(argv):
    """外層安全網：任何沒被 FormatError/KeyboardInterrupt/RestoreFailure 接住的意外例外
    （例如 id 沒驗乾淨、跑到一半路徑操作炸掉），統一印一行訊息、回新碼 7，而不是讓
    traceback 混進 exit code 1（那格已經被「還原失敗中止」佔用，撞碼會誤判）。"""
    try:
        return _main_impl(argv)
    except KeyboardInterrupt:
        # 正常情況下中斷已經在 _main_impl 的迴圈裡被接住、還原、回 130；這裡純粹是
        # 保險——萬一哪天中斷發生在迴圈之外（例如收尾階段），也不會落到下面的
        # except Exception 被誤判成內部錯誤。
        return 130
    except Exception as e:
        eprint("[錯誤] 未預期的內部錯誤：%s: %s" % (type(e).__name__, e))
        return EXIT_INTERNAL_ERROR


def _main_impl(argv):
    try:
        opts = parse_args(argv)
    except FormatError as e:
        eprint("[錯誤] %s" % e)
        return EXIT_FORMAT_ERROR

    try:
        cwd_abs, entries = load_mutations(opts["batch"], opts["cwd"])
    except FormatError as e:
        eprint("[錯誤] 格式錯誤：%s" % e)
        return EXIT_FORMAT_ERROR

    check_mode = opts["check"]
    # --check 且沒明講 --out 時不建 mutate-out/、不寫 summary/log；
    # 全批模式維持原預設（清單旁 mutate-out/），這是唯二會自動落地的情況。
    out_dir = opts["out"]
    if out_dir is None and not check_mode:
        out_dir = default_out_dir(opts["batch"])
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    _install_signal_handlers()

    rows = []
    n_pass = n_fail = n_na = n_cr = 0
    aborted = False

    for idx, entry in enumerate(entries):
        try:
            applied, compile_col, test_col, verdict, elapsed = run_entry(
                entry, cwd_abs, out_dir, check_mode)
        except KeyboardInterrupt:
            eprint("[中斷] 收到中止信號，已還原當前檔案（id=%s）" % entry["id"])
            if check_mode:
                _print_check_table(rows)
            else:
                _print_batch_table(rows, n_pass, n_fail, n_na, n_cr)
            _write_summary(out_dir, rows, check_mode, n_pass, n_fail, n_na, n_cr)
            return 130
        except RestoreFailure as e:
            eprint("[錯誤] %s" % e)
            if check_mode:
                _print_check_table(rows)
            else:
                _print_batch_table(rows, n_pass, n_fail, n_na, n_cr)
            _write_summary(out_dir, rows, check_mode, n_pass, n_fail, n_na, n_cr)
            return EXIT_RESTORE_FAILED

        if check_mode:
            rows.append((entry["id"], "yes" if applied else "no"))
            continue

        rows.append((entry["id"], "yes" if applied else "no", compile_col,
                     test_col, entry["expect"], verdict, str(elapsed)))

        if verdict == "PASS":
            n_pass += 1
        elif verdict == "FAIL":
            n_fail += 1
        elif verdict == "not-applied":
            n_na += 1
        elif verdict == "compile-red":
            n_cr += 1

        if idx == 0 and verdict != "PASS":
            aborted = True
            break

    if check_mode:
        _print_check_table(rows)
        _write_summary(out_dir, rows, check_mode)
        any_not_applied = any(r[1] == "no" for r in rows)
        return EXIT_NOT_APPLIED if any_not_applied else EXIT_OK

    _print_batch_table(rows, n_pass, n_fail, n_na, n_cr)
    _write_summary(out_dir, rows, check_mode, n_pass, n_fail, n_na, n_cr)

    if aborted:
        return EXIT_CONTROL_ABORT
    if n_na > 0:
        return EXIT_NOT_APPLIED
    if n_cr > 0:
        return EXIT_COMPILE_RED
    if n_fail > 0:
        return EXIT_FAIL
    return EXIT_OK


def _print_check_table(rows):
    print("id | applied")
    for r in rows:
        print(" | ".join(r))


def _print_batch_table(rows, n_pass, n_fail, n_na, n_cr):
    print("id | applied | compile | test | expect | verdict | secs")
    for r in rows:
        print(" | ".join(r))
    print("%d PASS / %d FAIL / %d not-applied / %d compile-red" %
          (n_pass, n_fail, n_na, n_cr))


def _write_summary(out_dir, rows, check_mode, n_pass=0, n_fail=0, n_na=0, n_cr=0):
    if not out_dir:
        return
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "summary.txt")
    with open(path, "w", encoding="utf-8") as f:
        if check_mode:
            f.write("id | applied\n")
            for r in rows:
                f.write(" | ".join(r) + "\n")
        else:
            f.write("id | applied | compile | test | expect | verdict | secs\n")
            for r in rows:
                f.write(" | ".join(r) + "\n")
            f.write("%d PASS / %d FAIL / %d not-applied / %d compile-red\n" %
                     (n_pass, n_fail, n_na, n_cr))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
