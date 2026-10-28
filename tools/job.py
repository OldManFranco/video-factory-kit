"""Run a long command DETACHED: it keeps running if Claude, the terminal or the app closes.
The log and the state go to <video>/work/jobs/. tools/status.py shows them.

Usage:
  python tools/job.py <video> <stage> -- <command ...>      launch (e.g. ... render -- tools/venv_render/bin/python tools/render_all.py "videos/x")
  python tools/job.py <video> list                          list jobs and their last log line
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vfk.kit import ROOT, Video, load, now, save  # noqa: E402


def alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, int(pid))            # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return code.value == 259                                  # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def detach(args, log):
    """Start a process that doesn't depend on this session."""
    if os.name != "nt":
        return subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=open(log, "ab"), stderr=subprocess.STDOUT,
                                start_new_session=True).pid
    flags = 0x00000008 | 0x00000200 | 0x01000000 | 0x08000000   # DETACHED | NEW_GROUP | BREAKAWAY_FROM_JOB | NO_WINDOW
    try:
        return subprocess.Popen(args, creationflags=flags, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, close_fds=True).pid
    except OSError:
        # the parent is inside a Windows "job" that doesn't allow breaking away: create it through WMI instead
        cmd = subprocess.list2cmdline(args).replace("'", "''")
        ps = (f"$si = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{{ShowWindow=[uint16]0}}; "
              f"$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
              f"-Arguments @{{CommandLine='{cmd}'; ProcessStartupInformation=$si}}; Write-Output $r.ProcessId")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
        return int(out.splitlines()[-1]) if out else None


def run_job(path):
    """Runs inside the detached process: the command, its log, exit code and end time."""
    job = load(path)
    job.update({"state": "running", "runner_pid": os.getpid(), "started": now()})
    save(path, job)
    with open(job["log"], "ab") as lg:
        lg.write(f"\n=== {now()} · {subprocess.list2cmdline(job['cmd'])}\n".encode("utf-8"))
        lg.flush()
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        p = subprocess.Popen(job["cmd"], stdout=lg, stderr=subprocess.STDOUT, cwd=job["cwd"], env=env,
                             creationflags=0x08000000 if os.name == "nt" else 0)
        job["pid"] = p.pid
        save(path, job)
        rc = p.wait()
    job.update({"state": "ok" if rc == 0 else "error", "exit": rc, "ended": now()})
    save(path, job)


def jobs(video):
    out = []
    for jp in sorted(video.jobs.glob("*.json")):
        j = load(jp, {})
        if j.get("state") in ("launched", "running") and not (alive(j.get("runner_pid")) or alive(j.get("pid"))):
            j.update({"state": "lost", "note": "interrupted (computer off or process killed): relaunch it; finished parts are cached"})
            save(jp, j)
        tail = ""
        if Path(j.get("log", "")).exists():
            with open(j["log"], "rb") as f:
                f.seek(max(0, os.path.getsize(j["log"]) - 800))
                lines = f.read().decode("utf-8", "replace").strip().splitlines()
                tail = lines[-1][-160:] if lines else ""
        out.append({**j, "last_line": tail})
    return out


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "_run":
        return run_job(sys.argv[2])
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    video = Video(sys.argv[1])
    if sys.argv[2] == "list":
        for j in jobs(video):
            print(f"{j['id']}  {j['state']:<8} {j.get('ended') or j.get('started') or j['launched']}  {j['last_line']}")
        return
    if "--" not in sys.argv:
        raise SystemExit(__doc__)
    stage, cmd = sys.argv[2], sys.argv[sys.argv.index("--") + 1:]
    if cmd and cmd[0] in ("python", "py-audio", "py-render"):
        cmd[0] = interpreter(cmd[0])
    video.jobs.mkdir(parents=True, exist_ok=True)
    jid = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{stage}"
    jp = video.jobs / f"{jid}.json"
    job = {"id": jid, "stage": stage, "cmd": cmd, "cwd": str(ROOT), "log": str(video.jobs / f"{jid}.log"),
           "state": "launched", "launched": now()}
    save(jp, job)
    pid = detach([sys.executable, str(Path(__file__).resolve()), "_run", str(jp)], job["log"])
    job = load(jp, job)
    job["runner_pid"] = job.get("runner_pid") or pid
    save(jp, job)
    print(f"OK job {jid} (pid {pid}) · log: {Path(job['log']).relative_to(ROOT).as_posix()}")


def interpreter(short):
    """'py-audio' / 'py-render' → the venv's python; 'python' → this one."""
    if short == "python":
        return sys.executable
    venv = ROOT / "tools" / ("venv_audio" if short == "py-audio" else "venv_render")
    exe = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not exe.exists():
        raise SystemExit(f"{venv} is missing: run the installer")
    return str(exe)


if __name__ == "__main__":
    main()
