use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::Manager;

const SIDECAR_PORT: &str = "8790";

struct SidecarProcess(Mutex<Option<Child>>);

impl Drop for SidecarProcess {
    fn drop(&mut self) {
        if let Ok(mut child) = self.0.lock() {
            if let Some(process) = child.as_mut() {
                let _ = process.kill();
            }
        }
    }
}

fn repo_root_from_manifest() -> Option<PathBuf> {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest.parent()?.parent()?.parent().map(PathBuf::from)
}

fn sidecar_locations(app: &tauri::App) -> Option<(PathBuf, PathBuf)> {
    if let Ok(resource_dir) = app.path().resource_dir() {
        let bundled_dir = resource_dir.join("astrabridge-sidecar");
        let bundled_exe = bundled_dir.join("astrabridge-sidecar.exe");
        if bundled_exe.exists() {
            return Some((bundled_exe, resource_dir));
        }
        let bundled_script = bundled_dir.join("sidecar_server.py");
        if bundled_script.exists() {
            return Some((bundled_script, resource_dir));
        }
    }
    let repo_root = repo_root_from_manifest()?;
    Some((
        repo_root.join("apps").join("astrabridge-sidecar").join("sidecar_server.py"),
        repo_root,
    ))
}

#[cfg(windows)]
fn stop_existing_astrabridge_sidecar_on_port() {
    let script = format!(
        r#"$ErrorActionPreference = 'SilentlyContinue';
$conn = Get-NetTCPConnection -LocalPort {port} -State Listen | Select-Object -First 1;
if ($conn) {{
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)";
  $cmd = [string]$proc.CommandLine;
  if ($cmd -match 'astrabridge-sidecar|astrabridge_sidecar\.server|sidecar_server\.py') {{
    taskkill /PID $($conn.OwningProcess) /T /F | Out-Null;
  }}
}}"#,
        port = SIDECAR_PORT
    );
    let _ = Command::new("powershell")
        .arg("-NoProfile")
        .arg("-ExecutionPolicy")
        .arg("Bypass")
        .arg("-Command")
        .arg(script)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

#[cfg(not(windows))]
fn stop_existing_astrabridge_sidecar_on_port() {}

fn spawn_sidecar(app: &tauri::App) -> Option<Child> {
    stop_existing_astrabridge_sidecar_on_port();
    let (sidecar, seed_root) = sidecar_locations(app)?;
    if !sidecar.exists() {
        eprintln!("AstraBridge sidecar was not found: {}", sidecar.display());
        return None;
    }

    let sidecar_is_exe = sidecar
        .extension()
        .and_then(|extension| extension.to_str())
        .map(|extension| extension.eq_ignore_ascii_case("exe"))
        .unwrap_or(false);

    if sidecar_is_exe {
        return Command::new(&sidecar)
            .arg("--serve")
            .arg("--port")
            .arg(SIDECAR_PORT)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .ok();
    }

    let mut candidates = Vec::new();
    if let Ok(path) = std::env::var("ASTRABRIDGE_PYTHON") {
        candidates.push(path);
    }
    if let Ok(path) = std::env::var("ASTRABRIDGE_PYTHON") {
        candidates.push(path);
    }
    candidates.push("python".to_string());
    candidates.push("py".to_string());

    for python in candidates {
        match Command::new(&python)
            .arg(&sidecar)
            .arg("--serve")
            .arg("--port")
            .arg(SIDECAR_PORT)
            .arg("--seed-root")
            .arg(&seed_root)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
        {
            Ok(child) => return Some(child),
            Err(error) => eprintln!("Could not start sidecar with {python}: {error}"),
        }
    }
    None
}

fn build_menu<R: tauri::Runtime>(handle: &tauri::AppHandle<R>) -> tauri::Result<Menu<R>> {
    let file_menu = Submenu::with_items(
        handle,
        "File",
        true,
        &[
            &MenuItem::with_id(handle, "file.new_project", "New Project", true, Some("Ctrl+Shift+N"))?,
            &MenuItem::with_id(handle, "file.open_project", "Open Project", true, None::<&str>)?,
            &PredefinedMenuItem::separator(handle)?,
            &PredefinedMenuItem::close_window(handle, None)?,
            &PredefinedMenuItem::quit(handle, None)?,
        ],
    )?;

    let project_menu = Submenu::with_items(
        handle,
        "Project",
        true,
        &[
            &MenuItem::with_id(handle, "project.recent", "Recent Projects", true, None::<&str>)?,
            &MenuItem::with_id(handle, "project.close", "Close Project", true, None::<&str>)?,
        ],
    )?;

    let thread_menu = Submenu::with_items(
        handle,
        "Thread",
        true,
        &[
            &MenuItem::with_id(handle, "thread.new", "New Thread", true, Some("Ctrl+N"))?,
            &MenuItem::with_id(handle, "thread.fork", "Fork Thread", true, None::<&str>)?,
            &MenuItem::with_id(handle, "thread.archive", "Archive Thread", true, None::<&str>)?,
        ],
    )?;

    let view_menu = Submenu::with_items(
        handle,
        "View",
        true,
        &[
            &MenuItem::with_id(handle, "view.command_palette", "Command Palette", true, Some("Ctrl+K"))?,
            &MenuItem::with_id(handle, "view.settings", "Settings", true, Some("Ctrl+,"))?,
            &MenuItem::with_id(handle, "view.inspector", "Toggle Inspector", true, None::<&str>)?,
        ],
    )?;

    let runtime_menu = Submenu::with_items(
        handle,
        "Runtime",
        true,
        &[
            &MenuItem::with_id(handle, "runtime.restart", "Restart Runtime", true, None::<&str>)?,
            &MenuItem::with_id(handle, "runtime.reload_models", "Reload Models", true, None::<&str>)?,
            &MenuItem::with_id(handle, "runtime.official_codex", "Official Codex", true, None::<&str>)?,
        ],
    )?;

    let help_menu = Submenu::with_items(
        handle,
        "Help",
        true,
        &[
            &MenuItem::with_id(handle, "help.about", "About AstraBridge", true, None::<&str>)?,
        ],
    )?;

    Menu::with_items(
        handle,
        &[&file_menu, &project_menu, &thread_menu, &view_menu, &runtime_menu, &help_menu],
    )
}

#[tauri::command]
fn sidecar_url() -> String {
    format!("http://127.0.0.1:{SIDECAR_PORT}")
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .menu(build_menu)
        .setup(|app| {
            app.manage(SidecarProcess(Mutex::new(spawn_sidecar(app))));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar_url])
        .run(tauri::generate_context!())
        .expect("error while running AstraBridge");
}

