use chrono::Local;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const SIDECAR_LAUNCH_RECORD_SCHEMA_VERSION: &str = "astrabridge-desktop-sidecar-launch-v1";
const SIDECAR_LEASE_SCHEMA_VERSION: &str = "astrabridge-desktop-sidecar-lease-v1";
const SIDECAR_READY_ROUTE: &str = "/readyz";
const SIDECAR_SHUTDOWN_ROUTE: &str = "/host/shutdown";
const MAX_LOG_ROTATIONS: usize = 4;
const MAX_ACTIVE_LOG_BYTES: u64 = 1_000_000;
const DEFAULT_READY_TIMEOUT_MS: u64 = 15_000;
const DEFAULT_SHUTDOWN_TIMEOUT_MS: u64 = 6_000;
const DEFAULT_MONITOR_POLL_MS: u64 = 800;
const DEFAULT_BACKOFF_BASE_MS: u64 = 750;
const DEFAULT_BACKOFF_MAX_MS: u64 = 5_000;
const DEFAULT_CIRCUIT_WINDOW_MS: u64 = 30_000;
const DEFAULT_CIRCUIT_OPEN_MS: u64 = 30_000;
const DEFAULT_CIRCUIT_FAILURE_LIMIT: u32 = 3;

#[derive(Clone, Debug)]
pub struct SidecarSupervisorTuning {
    pub ready_timeout: Duration,
    pub shutdown_timeout: Duration,
    pub monitor_poll: Duration,
    pub restart_backoff_base: Duration,
    pub restart_backoff_max: Duration,
    pub circuit_window: Duration,
    pub circuit_open: Duration,
    pub circuit_failure_limit: u32,
}

impl Default for SidecarSupervisorTuning {
    fn default() -> Self {
        Self {
            ready_timeout: Duration::from_millis(DEFAULT_READY_TIMEOUT_MS),
            shutdown_timeout: Duration::from_millis(DEFAULT_SHUTDOWN_TIMEOUT_MS),
            monitor_poll: Duration::from_millis(DEFAULT_MONITOR_POLL_MS),
            restart_backoff_base: Duration::from_millis(DEFAULT_BACKOFF_BASE_MS),
            restart_backoff_max: Duration::from_millis(DEFAULT_BACKOFF_MAX_MS),
            circuit_window: Duration::from_millis(DEFAULT_CIRCUIT_WINDOW_MS),
            circuit_open: Duration::from_millis(DEFAULT_CIRCUIT_OPEN_MS),
            circuit_failure_limit: DEFAULT_CIRCUIT_FAILURE_LIMIT,
        }
    }
}

#[derive(Clone, Debug)]
pub struct SidecarLaunchConfig {
    pub sidecar_path: PathBuf,
    pub seed_root: PathBuf,
    pub state_root: PathBuf,
    pub build_version: String,
    pub python_candidates: Vec<String>,
    pub extra_env: HashMap<String, String>,
    pub tuning: SidecarSupervisorTuning,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct SidecarLaunchOwner {
    kind: String,
    instance_id: String,
    desktop_pid: u32,
    seed_root: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct SidecarLaunchRecord {
    schema_version: String,
    status: String,
    boot_id: String,
    pid: u32,
    listen_host: String,
    listen_port: Option<u16>,
    requested_port: u16,
    build_version: String,
    runtime_version: Option<String>,
    durable_run_store_schema_version: Option<String>,
    project_schema_version: Option<String>,
    created_at: String,
    updated_at: String,
    ready_at: Option<String>,
    exited_at: Option<String>,
    executable: String,
    seed_root: String,
    source_root: Option<String>,
    repo_root: Option<String>,
    current_source_match: Option<bool>,
    owner: SidecarLaunchOwner,
    log_paths: HashMap<String, String>,
    startup_restore: Option<Value>,
    last_error: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct SidecarLeaseRecord {
    schema_version: String,
    instance_id: String,
    desktop_pid: u32,
    created_at: String,
    updated_at: String,
    state_root: String,
    seed_root: String,
}

#[derive(Clone, Debug, Deserialize)]
struct ReadySidecar {
    pid: Option<u32>,
    listen_port: Option<u16>,
}

#[derive(Clone, Debug, Deserialize)]
struct ReadyPayload {
    ok: bool,
    boot_id: String,
    build_version: String,
    runtime_version: String,
    durable_run_store_schema_version: String,
    project_schema_version: String,
    listen_port: Option<u16>,
    sidecar: Option<ReadySidecar>,
    startup_restore: Option<Value>,
}

#[derive(Clone, Debug)]
struct SidecarBinding {
    url: String,
    port: u16,
    pid: u32,
    boot_id: String,
}

struct SupervisorState {
    binding: Option<SidecarBinding>,
    child: Option<Child>,
    status: String,
    start_requested: bool,
    starting: bool,
    last_error: Option<String>,
    failure_window_started_at: Option<Instant>,
    consecutive_failures: u32,
    backoff_until: Option<Instant>,
    circuit_open_until: Option<Instant>,
    last_probe_at: Option<Instant>,
}

impl Default for SupervisorState {
    fn default() -> Self {
        Self {
            binding: None,
            child: None,
            status: "starting".to_string(),
            start_requested: true,
            starting: false,
            last_error: None,
            failure_window_started_at: None,
            consecutive_failures: 0,
            backoff_until: None,
            circuit_open_until: None,
            last_probe_at: None,
        }
    }
}

struct SupervisorInner {
    config: SidecarLaunchConfig,
    instance_id: String,
    state: Mutex<SupervisorState>,
    condvar: Condvar,
    shutdown_requested: AtomicBool,
}

#[derive(Clone)]
pub struct SidecarSupervisor {
    inner: Arc<SupervisorInner>,
}

pub fn apply_common_sidecar_environment(command: &mut Command, extra_env: &HashMap<String, String>) {
    command.env_remove("CODEX_HOME");
    command.env_remove("ASTRABRIDGE_CODEX_HOME");
    for (key, value) in extra_env {
        command.env(key, value);
    }
}

impl SidecarLaunchConfig {
    fn launch_record_path(&self) -> PathBuf {
        self.state_root.join("sidecar-launch.json")
    }

    fn leases_root(&self) -> PathBuf {
        self.state_root.join("leases")
    }

    fn logs_root(&self) -> PathBuf {
        self.state_root.join("logs")
    }

    fn stdout_log_path(&self) -> PathBuf {
        self.logs_root().join("sidecar.stdout.log")
    }

    fn stderr_log_path(&self) -> PathBuf {
        self.logs_root().join("sidecar.stderr.log")
    }

    fn lineage_log_path(&self) -> PathBuf {
        self.logs_root().join("sidecar-host.jsonl")
    }

    fn ensure_state_paths(&self) -> Result<(), String> {
        fs::create_dir_all(&self.state_root).map_err(|error| format!("Could not create sidecar state root: {error}"))?;
        fs::create_dir_all(self.leases_root()).map_err(|error| format!("Could not create sidecar lease root: {error}"))?;
        fs::create_dir_all(self.logs_root()).map_err(|error| format!("Could not create sidecar log root: {error}"))?;
        Ok(())
    }
}

impl SupervisorInner {
    fn lease_path(&self) -> PathBuf {
        self.config
            .leases_root()
            .join(format!("lease-{}.json", self.instance_id))
    }

    fn now_iso(&self) -> String {
        Local::now().to_rfc3339()
    }

    fn new_instance_id(&self, prefix: &str) -> String {
        format!(
            "{prefix}-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis()
        )
    }

    fn write_current_lease(&self) -> Result<(), String> {
        let payload = SidecarLeaseRecord {
            schema_version: SIDECAR_LEASE_SCHEMA_VERSION.to_string(),
            instance_id: self.instance_id.clone(),
            desktop_pid: std::process::id(),
            created_at: self.now_iso(),
            updated_at: self.now_iso(),
            state_root: self.config.state_root.display().to_string(),
            seed_root: self.config.seed_root.display().to_string(),
        };
        self.write_json_atomic(&self.lease_path(), &payload)
    }

    fn remove_current_lease(&self) {
        let _ = fs::remove_file(self.lease_path());
    }

    fn write_json_atomic<T: Serialize>(&self, path: &Path, payload: &T) -> Result<(), String> {
        let serialized = serde_json::to_vec_pretty(payload).map_err(|error| format!("Could not serialize JSON: {error}"))?;
        let temp_path = path.with_extension(format!(
            "tmp-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis()
        ));
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|error| format!("Could not create JSON parent directory: {error}"))?;
        }
        fs::write(&temp_path, serialized).map_err(|error| format!("Could not write temporary JSON file: {error}"))?;
        fs::rename(&temp_path, path).map_err(|error| format!("Could not replace JSON file atomically: {error}"))?;
        Ok(())
    }

    fn read_launch_record(&self) -> Result<Option<SidecarLaunchRecord>, String> {
        let path = self.config.launch_record_path();
        if !path.exists() {
            return Ok(None);
        }
        let text = fs::read_to_string(&path).map_err(|error| format!("Could not read sidecar launch record: {error}"))?;
        let parsed = serde_json::from_str::<SidecarLaunchRecord>(&text)
            .map_err(|error| format!("Could not parse sidecar launch record: {error}"))?;
        Ok(Some(parsed))
    }

    fn append_lineage_event(&self, event_type: &str, payload: Value) {
        let path = self.config.lineage_log_path();
        let record = json!({
            "ts": self.now_iso(),
            "event": event_type,
            "instance_id": self.instance_id,
            "payload": payload,
        });
        let rendered = redact_log_text(&serde_json::to_string(&record).unwrap_or_else(|_| "{\"event\":\"serialization_failed\"}".to_string()));
        let _ = append_line(&path, &(rendered + "\n"));
    }

    fn cleanup_stale_leases(&self) -> usize {
        let leases_root = self.config.leases_root();
        let mut active = 0usize;
        let entries = match fs::read_dir(&leases_root) {
            Ok(entries) => entries,
            Err(_) => return 0,
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            let text = match fs::read_to_string(&path) {
                Ok(text) => text,
                Err(_) => {
                    let _ = fs::remove_file(&path);
                    continue;
                }
            };
            let parsed = match serde_json::from_str::<SidecarLeaseRecord>(&text) {
                Ok(parsed) => parsed,
                Err(_) => {
                    let _ = fs::remove_file(&path);
                    continue;
                }
            };
            if parsed.state_root != self.config.state_root.display().to_string() {
                continue;
            }
            if process_is_running(parsed.desktop_pid) {
                active += 1;
                continue;
            }
            let _ = fs::remove_file(&path);
            self.append_lineage_event(
                "stale_lease_reaped",
                json!({
                    "lease_path": path.display().to_string(),
                    "desktop_pid": parsed.desktop_pid,
                }),
            );
        }
        active
    }

    fn preferred_restart_port(&self) -> u16 {
        if let Ok(Some(record)) = self.read_launch_record() {
            if record.seed_root == self.config.seed_root.display().to_string() {
                if let Some(port) = record.listen_port {
                    if port != 0 && port_is_available(port) {
                        return port;
                    }
                }
            }
        }
        0
    }

    fn lineage_paths(&self) -> HashMap<String, String> {
        HashMap::from([
            ("stdout".to_string(), self.config.stdout_log_path().display().to_string()),
            ("stderr".to_string(), self.config.stderr_log_path().display().to_string()),
            ("lineage".to_string(), self.config.lineage_log_path().display().to_string()),
        ])
    }

    fn write_starting_launch_record(
        &self,
        boot_id: &str,
        pid: u32,
        requested_port: u16,
        executable: &str,
        last_error: Option<String>,
    ) -> Result<(), String> {
        let now = self.now_iso();
        let payload = SidecarLaunchRecord {
            schema_version: SIDECAR_LAUNCH_RECORD_SCHEMA_VERSION.to_string(),
            status: "starting".to_string(),
            boot_id: boot_id.to_string(),
            pid,
            listen_host: "127.0.0.1".to_string(),
            listen_port: if requested_port == 0 { None } else { Some(requested_port) },
            requested_port,
            build_version: self.config.build_version.clone(),
            runtime_version: None,
            durable_run_store_schema_version: None,
            project_schema_version: None,
            created_at: now.clone(),
            updated_at: now,
            ready_at: None,
            exited_at: None,
            executable: executable.to_string(),
            seed_root: self.config.seed_root.display().to_string(),
            source_root: None,
            repo_root: None,
            current_source_match: None,
            owner: SidecarLaunchOwner {
                kind: "astrabridge-desktop".to_string(),
                instance_id: self.instance_id.clone(),
                desktop_pid: std::process::id(),
                seed_root: self.config.seed_root.display().to_string(),
            },
            log_paths: self.lineage_paths(),
            startup_restore: None,
            last_error,
        };
        self.write_json_atomic(&self.config.launch_record_path(), &payload)
    }

    fn update_launch_record_status(
        &self,
        status: &str,
        boot_id: &str,
        pid: u32,
        listen_port: Option<u16>,
        last_error: Option<String>,
    ) {
        let existing = self.read_launch_record().ok().flatten();
        let now = self.now_iso();
        let created_at = existing
            .as_ref()
            .map(|record| record.created_at.clone())
            .unwrap_or_else(|| now.clone());
        let payload = SidecarLaunchRecord {
            schema_version: SIDECAR_LAUNCH_RECORD_SCHEMA_VERSION.to_string(),
            status: status.to_string(),
            boot_id: boot_id.to_string(),
            pid,
            listen_host: "127.0.0.1".to_string(),
            listen_port,
            requested_port: existing.as_ref().map(|record| record.requested_port).unwrap_or(listen_port.unwrap_or(0)),
            build_version: self.config.build_version.clone(),
            runtime_version: existing.as_ref().and_then(|record| record.runtime_version.clone()),
            durable_run_store_schema_version: existing
                .as_ref()
                .and_then(|record| record.durable_run_store_schema_version.clone()),
            project_schema_version: existing
                .as_ref()
                .and_then(|record| record.project_schema_version.clone()),
            created_at,
            updated_at: now.clone(),
            ready_at: if status == "ready" {
                Some(now.clone())
            } else {
                existing.as_ref().and_then(|record| record.ready_at.clone())
            },
            exited_at: if status == "stopped" { Some(now.clone()) } else { None },
            executable: existing
                .as_ref()
                .map(|record| record.executable.clone())
                .unwrap_or_default(),
            seed_root: self.config.seed_root.display().to_string(),
            source_root: existing.as_ref().and_then(|record| record.source_root.clone()),
            repo_root: existing.as_ref().and_then(|record| record.repo_root.clone()),
            current_source_match: existing.as_ref().and_then(|record| record.current_source_match),
            owner: existing
                .as_ref()
                .map(|record| record.owner.clone())
                .unwrap_or(SidecarLaunchOwner {
                    kind: "astrabridge-desktop".to_string(),
                    instance_id: self.instance_id.clone(),
                    desktop_pid: std::process::id(),
                    seed_root: self.config.seed_root.display().to_string(),
                }),
            log_paths: existing
                .as_ref()
                .map(|record| record.log_paths.clone())
                .unwrap_or_else(|| self.lineage_paths()),
            startup_restore: existing.as_ref().and_then(|record| record.startup_restore.clone()),
            last_error,
        };
        let _ = self.write_json_atomic(&self.config.launch_record_path(), &payload);
    }

    fn monitor_loop(self: Arc<Self>) {
        loop {
            if self.shutdown_requested.load(Ordering::SeqCst) {
                return;
            }
            let _ = self.cleanup_stale_leases();
            let mut binding_to_probe: Option<SidecarBinding> = None;
            let mut should_start = false;
            {
                let mut state = self.state.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
                if let Some(deadline) = state.circuit_open_until {
                    if Instant::now() >= deadline {
                        state.circuit_open_until = None;
                        state.start_requested = true;
                        state.status = "recovering".to_string();
                    }
                }
                let binding_snapshot = state.binding.clone();
                if let Some(child) = state.child.as_mut() {
                    match child.try_wait() {
                        Ok(Some(status)) => {
                            let pid = binding_snapshot
                                .as_ref()
                                .map(|binding| binding.pid)
                                .unwrap_or_else(|| child.id());
                            let boot_id = binding_snapshot
                                .as_ref()
                                .map(|binding| binding.boot_id.clone())
                                .unwrap_or_default();
                            let port = binding_snapshot.as_ref().map(|binding| binding.port);
                            let _ = child.wait();
                            state.child = None;
                            state.binding = None;
                            state.start_requested = true;
                            state.last_error = Some(format!("Sidecar exited with status {status}."));
                            self.update_launch_record_status(
                                "stopped",
                                &boot_id,
                                pid,
                                port,
                                state.last_error.clone(),
                            );
                            self.append_lineage_event(
                                "sidecar_exit_observed",
                                json!({
                                    "pid": pid,
                                    "boot_id": boot_id,
                                    "status": format!("{status}"),
                                }),
                            );
                        }
                        Ok(None) => {}
                        Err(error) => {
                            state.last_error = Some(format!("Could not check sidecar process: {error}"));
                        }
                    }
                }
                if let Some(binding) = state.binding.clone() {
                    let should_probe = state
                        .last_probe_at
                        .map(|instant| instant.elapsed() >= self.config.tuning.monitor_poll)
                        .unwrap_or(true);
                    if should_probe {
                        state.last_probe_at = Some(Instant::now());
                        binding_to_probe = Some(binding);
                    }
                }
                if state.start_requested
                    && !state.starting
                    && state.circuit_open_until.is_none()
                    && state
                        .backoff_until
                        .map(|instant| Instant::now() >= instant)
                        .unwrap_or(true)
                {
                    should_start = true;
                    state.starting = true;
                    state.status = "starting".to_string();
                }
            }
            if let Some(binding) = binding_to_probe {
                if self
                    .probe_ready_binding(binding.port, &binding.boot_id)
                    .map(|ready| ready.boot_id == binding.boot_id)
                    .unwrap_or(false)
                {
                    // still healthy
                } else {
                    let mut state = self.state.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
                    if state
                        .binding
                        .as_ref()
                        .map(|current| current.boot_id == binding.boot_id)
                        .unwrap_or(false)
                    {
                        state.binding = None;
                        state.child = None;
                        state.start_requested = true;
                        state.last_error = Some(format!(
                            "Sidecar readiness probe failed for boot {} on port {}.",
                            binding.boot_id, binding.port
                        ));
                        self.append_lineage_event(
                            "sidecar_readyz_probe_failed",
                            json!({
                                "boot_id": binding.boot_id,
                                "port": binding.port,
                            }),
                        );
                    }
                }
            }
            if should_start {
                self.start_or_reattach();
            }
            thread::sleep(self.config.tuning.monitor_poll);
        }
    }

    fn start_or_reattach(&self) {
        let result = match self.try_adopt_existing() {
            Ok(Some(binding)) => {
                self.append_lineage_event(
                    "sidecar_adopted",
                    json!({
                        "boot_id": binding.boot_id,
                        "pid": binding.pid,
                        "port": binding.port,
                    }),
                );
                Ok((binding, None))
            }
            Ok(None) => self.spawn_and_wait().map(|(binding, child)| (binding, Some(child))),
            Err(error) => Err(error),
        };

        let mut state = self.state.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        match result {
            Ok((binding, child)) => {
                state.binding = Some(binding);
                state.child = child;
                state.status = "ready".to_string();
                state.start_requested = false;
                state.starting = false;
                state.last_error = None;
                state.failure_window_started_at = None;
                state.consecutive_failures = 0;
                state.backoff_until = None;
                state.circuit_open_until = None;
                state.last_probe_at = Some(Instant::now());
            }
            Err(error) => {
                state.binding = None;
                state.child = None;
                state.starting = false;
                state.last_error = Some(error.clone());
                let now = Instant::now();
                let reset_window = state
                    .failure_window_started_at
                    .map(|started| now.duration_since(started) > self.config.tuning.circuit_window)
                    .unwrap_or(true);
                if reset_window {
                    state.failure_window_started_at = Some(now);
                    state.consecutive_failures = 0;
                }
                state.consecutive_failures += 1;
                if state.consecutive_failures >= self.config.tuning.circuit_failure_limit {
                    state.circuit_open_until = Some(now + self.config.tuning.circuit_open);
                    state.backoff_until = None;
                    state.start_requested = false;
                    state.status = "circuit_open".to_string();
                    self.append_lineage_event(
                        "sidecar_circuit_breaker_opened",
                        json!({
                            "failures": state.consecutive_failures,
                            "last_error": state.last_error,
                            "lineage_log": self.config.lineage_log_path().display().to_string(),
                        }),
                    );
                } else {
                    let backoff = exponential_backoff(
                        self.config.tuning.restart_backoff_base,
                        self.config.tuning.restart_backoff_max,
                        state.consecutive_failures,
                    );
                    state.backoff_until = Some(now + backoff);
                    state.start_requested = true;
                    state.status = "waiting_retry".to_string();
                }
                self.update_launch_record_status(
                    "failed",
                    "",
                    0,
                    None,
                    state.last_error.clone(),
                );
            }
        }
        self.condvar.notify_all();
    }

    fn try_adopt_existing(&self) -> Result<Option<SidecarBinding>, String> {
        let Some(record) = self.read_launch_record()? else {
            return Ok(None);
        };
        if record.seed_root != self.config.seed_root.display().to_string() {
            return Ok(None);
        }
        let port = match record.listen_port {
            Some(port) if port != 0 => port,
            _ => return Ok(None),
        };
        if !process_is_running(record.pid) {
            self.append_lineage_event(
                "launch_record_stale",
                json!({
                    "boot_id": record.boot_id,
                    "pid": record.pid,
                    "port": port,
                }),
            );
            return Ok(None);
        }
        let ready = self.probe_ready_binding(port, &record.boot_id)?;
        if !ready.ok || ready.build_version != self.config.build_version {
            return Ok(None);
        }
        let pid = ready
            .sidecar
            .as_ref()
            .and_then(|sidecar| sidecar.pid)
            .unwrap_or(record.pid);
        let resolved_port = ready
            .sidecar
            .as_ref()
            .and_then(|sidecar| sidecar.listen_port)
            .or(ready.listen_port)
            .unwrap_or(port);
        Ok(Some(SidecarBinding {
            url: format!("http://127.0.0.1:{resolved_port}"),
            port: resolved_port,
            pid,
            boot_id: ready.boot_id,
        }))
    }

    fn spawn_and_wait(&self) -> Result<(SidecarBinding, Child), String> {
        rotate_log_if_large(&self.config.stdout_log_path(), MAX_ACTIVE_LOG_BYTES, MAX_LOG_ROTATIONS)?;
        rotate_log_if_large(&self.config.stderr_log_path(), MAX_ACTIVE_LOG_BYTES, MAX_LOG_ROTATIONS)?;
        rotate_log_if_large(&self.config.lineage_log_path(), MAX_ACTIVE_LOG_BYTES, MAX_LOG_ROTATIONS)?;

        let requested_port = self.preferred_restart_port();
        let boot_id = self.new_instance_id("sidecar-boot");
        let mut errors = Vec::new();
        let script_mode = self
            .config
            .sidecar_path
            .extension()
            .and_then(|extension| extension.to_str())
            .map(|extension| !extension.eq_ignore_ascii_case("exe"))
            .unwrap_or(true);

        if !self.config.sidecar_path.exists() {
            return Err(format!(
                "Desktop sidecar executable was not found: {}",
                self.config.sidecar_path.display()
            ));
        }

        if script_mode {
            for python in &self.config.python_candidates {
                match self.try_spawn_with_program(
                    python,
                    Some(self.config.sidecar_path.as_path()),
                    requested_port,
                    &boot_id,
                ) {
                    Ok((binding, child)) => return Ok((binding, child)),
                    Err(error) => errors.push(format!("{python}: {error}")),
                }
            }
            return Err(format!(
                "Could not start the AstraBridge sidecar with any Python launcher. {}",
                errors.join(" | ")
            ));
        }

        self.try_spawn_with_program(
            self.config.sidecar_path.to_string_lossy().as_ref(),
            None,
            requested_port,
            &boot_id,
        )
    }

    fn try_spawn_with_program(
        &self,
        program: &str,
        script_path: Option<&Path>,
        requested_port: u16,
        boot_id: &str,
    ) -> Result<(SidecarBinding, Child), String> {
        let mut command = Command::new(program);
        apply_common_sidecar_environment(&mut command, &self.config.extra_env);
        command.current_dir(&self.config.seed_root);
        if let Some(script_path) = script_path {
            command.arg(script_path);
        }
        command
            .arg("--serve")
            .arg("--port")
            .arg(requested_port.to_string())
            .arg("--seed-root")
            .arg(&self.config.seed_root)
            .arg("--boot-id")
            .arg(boot_id)
            .arg("--launch-record")
            .arg(self.config.launch_record_path())
            .arg("--build-version")
            .arg(&self.config.build_version)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = command
            .spawn()
            .map_err(|error| format!("Could not spawn desktop sidecar: {error}"))?;
        let pid = child.id();
        self.write_starting_launch_record(
            boot_id,
            pid,
            requested_port,
            program,
            None,
        )?;
        if let Some(stdout) = child.stdout.take() {
            let path = self.config.stdout_log_path();
            let boot = boot_id.to_string();
            thread::spawn(move || pump_child_output(stdout, path, "stdout", &boot));
        }
        if let Some(stderr) = child.stderr.take() {
            let path = self.config.stderr_log_path();
            let boot = boot_id.to_string();
            thread::spawn(move || pump_child_output(stderr, path, "stderr", &boot));
        }
        self.append_lineage_event(
            "sidecar_launch_requested",
            json!({
                "boot_id": boot_id,
                "pid": pid,
                "requested_port": requested_port,
                "program": program,
                "script_path": script_path.map(|path| path.display().to_string()),
            }),
        );
        let binding = self.wait_for_ready(&mut child, boot_id, pid)?;
        Ok((binding, child))
    }

    fn wait_for_ready(
        &self,
        child: &mut Child,
        boot_id: &str,
        pid: u32,
    ) -> Result<SidecarBinding, String> {
        let deadline = Instant::now() + self.config.tuning.ready_timeout;
        loop {
            if let Ok(Some(status)) = child.try_wait() {
                let message = format!("Desktop sidecar exited before readiness for boot {boot_id}: {status}");
                self.append_lineage_event(
                    "sidecar_launch_failed",
                    json!({
                        "boot_id": boot_id,
                        "pid": pid,
                        "reason": message,
                    }),
                );
                return Err(message);
            }
            if let Ok(Some(record)) = self.read_launch_record() {
                if record.boot_id == boot_id {
                    if let Some(port) = record.listen_port {
                        if let Ok(ready) = self.probe_ready_binding(port, boot_id) {
                            let resolved_port = ready
                                .sidecar
                                .as_ref()
                                .and_then(|sidecar| sidecar.listen_port)
                                .or(ready.listen_port)
                                .unwrap_or(port);
                            let resolved_pid = ready
                                .sidecar
                                .as_ref()
                                .and_then(|sidecar| sidecar.pid)
                                .unwrap_or(pid);
                            self.append_lineage_event(
                                "sidecar_launch_ready",
                                json!({
                                    "boot_id": boot_id,
                                    "pid": resolved_pid,
                                    "port": resolved_port,
                                    "startup_restore": ready.startup_restore,
                                }),
                            );
                            return Ok(SidecarBinding {
                                url: format!("http://127.0.0.1:{resolved_port}"),
                                port: resolved_port,
                                pid: resolved_pid,
                                boot_id: ready.boot_id,
                            });
                        }
                    }
                }
            }
            if Instant::now() >= deadline {
                let message = format!(
                    "Desktop sidecar did not become ready within {} ms for boot {boot_id}. Review {}.",
                    self.config.tuning.ready_timeout.as_millis(),
                    self.config.lineage_log_path().display()
                );
                self.append_lineage_event(
                    "sidecar_launch_timed_out",
                    json!({
                        "boot_id": boot_id,
                        "pid": pid,
                        "reason": message,
                    }),
                );
                let _ = self.hard_kill_verified(pid, boot_id);
                return Err(message);
            }
            thread::sleep(Duration::from_millis(200));
        }
    }

    fn probe_ready_binding(&self, port: u16, expected_boot_id: &str) -> Result<ReadyPayload, String> {
        let body = http_json_request(port, "GET", SIDECAR_READY_ROUTE, None)?;
        let payload = serde_json::from_value::<ReadyPayload>(body)
            .map_err(|error| format!("Could not parse sidecar readiness payload: {error}"))?;
        if !payload.ok {
            return Err(format!("Desktop sidecar readiness probe returned ok=false on port {port}."));
        }
        if payload.boot_id != expected_boot_id {
            return Err(format!(
                "Desktop sidecar readiness boot mismatch on port {port}: expected {expected_boot_id}, got {}.",
                payload.boot_id
            ));
        }
        if payload.build_version != self.config.build_version {
            return Err(format!(
                "Desktop sidecar build mismatch on port {port}: expected {}, got {}.",
                self.config.build_version, payload.build_version
            ));
        }
        if payload.runtime_version.trim().is_empty() {
            return Err(format!("Desktop sidecar readiness runtime version was empty on port {port}."));
        }
        if payload.durable_run_store_schema_version.trim().is_empty() {
            return Err(format!(
                "Desktop sidecar readiness durable run-store schema version was empty on port {port}."
            ));
        }
        if payload.project_schema_version.trim().is_empty() {
            return Err(format!("Desktop sidecar readiness project schema version was empty on port {port}."));
        }
        Ok(payload)
    }

    fn request_graceful_shutdown(&self, binding: &SidecarBinding) -> Result<(), String> {
        self.append_lineage_event(
            "sidecar_graceful_shutdown_requested",
            json!({
                "boot_id": binding.boot_id,
                "pid": binding.pid,
                "port": binding.port,
            }),
        );
        let request = json!({ "boot_id": binding.boot_id });
        let _ = http_json_request(
            binding.port,
            "POST",
            SIDECAR_SHUTDOWN_ROUTE,
            Some(request.to_string().as_str()),
        )?;
        let deadline = Instant::now() + self.config.tuning.shutdown_timeout;
        while Instant::now() < deadline {
            if !process_is_running(binding.pid) {
                self.append_lineage_event(
                    "sidecar_graceful_shutdown_succeeded",
                    json!({
                        "boot_id": binding.boot_id,
                        "pid": binding.pid,
                    }),
                );
                return Ok(());
            }
            thread::sleep(Duration::from_millis(150));
        }
        Err(format!(
            "Desktop sidecar did not exit after graceful shutdown within {} ms.",
            self.config.tuning.shutdown_timeout.as_millis()
        ))
    }

    fn hard_kill_verified(&self, pid: u32, boot_id: &str) -> Result<(), String> {
        if pid == 0 || boot_id.trim().is_empty() {
            return Ok(());
        }
        let record = self.read_launch_record()?.ok_or_else(|| "No launch record was available for hard kill verification.".to_string())?;
        if record.pid != pid || record.boot_id != boot_id {
            return Err(format!(
                "Refused to hard-kill sidecar pid {pid}: launch record ownership mismatch for boot {boot_id}."
            ));
        }
        if !process_is_running(pid) {
            return Ok(());
        }
        terminate_process_tree(pid)?;
        self.append_lineage_event(
            "sidecar_hard_kill_succeeded",
            json!({
                "boot_id": boot_id,
                "pid": pid,
            }),
        );
        Ok(())
    }

    fn diagnostic_message(&self, state: &SupervisorState, fallback: &str) -> String {
        let last_error = state.last_error.clone().unwrap_or_else(|| fallback.to_string());
        format!(
            "{last_error} Review the desktop sidecar lineage log at {}.",
            self.config.lineage_log_path().display()
        )
    }

    fn begin_shutdown(&self) {
        if self.shutdown_requested.swap(true, Ordering::SeqCst) {
            return;
        }
        self.condvar.notify_all();
        self.remove_current_lease();
        let remaining_leases = self.cleanup_stale_leases();
        let binding = {
            let mut state = self.state.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
            let binding = state.binding.clone();
            state.child = None;
            state.binding = None;
            state.status = "stopped".to_string();
            binding
        };
        if remaining_leases == 0 {
            if let Some(binding) = binding {
                if let Err(error) = self.request_graceful_shutdown(&binding) {
                    self.append_lineage_event(
                        "sidecar_graceful_shutdown_failed",
                        json!({
                            "boot_id": binding.boot_id,
                            "pid": binding.pid,
                            "error": error,
                        }),
                    );
                    let _ = self.hard_kill_verified(binding.pid, &binding.boot_id);
                }
            }
        }
    }
}

impl SidecarSupervisor {
    pub fn new(config: SidecarLaunchConfig) -> Result<Self, String> {
        config.ensure_state_paths()?;
        let instance_id = format!(
            "desktop-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis()
        );
        let inner = Arc::new(SupervisorInner {
            config,
            instance_id,
            state: Mutex::new(SupervisorState::default()),
            condvar: Condvar::new(),
            shutdown_requested: AtomicBool::new(false),
        });
        inner.write_current_lease()?;
        inner.append_lineage_event(
            "desktop_sidecar_supervision_started",
            json!({
                "seed_root": inner.config.seed_root.display().to_string(),
                "state_root": inner.config.state_root.display().to_string(),
                "build_version": inner.config.build_version,
            }),
        );
        let monitor = inner.clone();
        thread::spawn(move || monitor.monitor_loop());
        Ok(Self { inner })
    }

    pub fn sidecar_url(&self) -> Result<String, String> {
        let deadline = Instant::now() + self.inner.config.tuning.ready_timeout;
        loop {
            let mut state = self.inner.state.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
            if let Some(binding) = state.binding.clone() {
                return Ok(binding.url);
            }
            if let Some(circuit_open_until) = state.circuit_open_until {
                if Instant::now() < circuit_open_until {
                    return Err(self
                        .inner
                        .diagnostic_message(&state, "Desktop sidecar supervision opened a circuit breaker after repeated launch failures."));
                }
            }
            if !state.start_requested && !state.starting {
                state.start_requested = true;
                self.inner.condvar.notify_all();
            }
            if Instant::now() >= deadline {
                return Err(self
                    .inner
                    .diagnostic_message(&state, "Desktop sidecar readiness timed out."));
            }
            let wait = self
                .inner
                .condvar
                .wait_timeout(state, Duration::from_millis(200))
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            state = wait.0;
            drop(state);
        }
    }

    #[cfg(test)]
    fn binding_for_test(&self) -> Option<SidecarBinding> {
        self.inner
            .state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .binding
            .clone()
    }
}

impl Drop for SidecarSupervisor {
    fn drop(&mut self) {
        self.inner.begin_shutdown();
    }
}

fn append_line(path: &Path, line: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| format!("Could not create log directory: {error}"))?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| format!("Could not open log file {}: {error}", path.display()))?;
    file.write_all(line.as_bytes())
        .map_err(|error| format!("Could not append log file {}: {error}", path.display()))?;
    Ok(())
}

fn redact_log_text(text: &str) -> String {
    let mut clean = text.to_string();
    for marker in [
        "api_key=",
        "apikey=",
        "token=",
        "password=",
        "secret=",
        "\"api_key\":\"",
        "\"apikey\":\"",
        "\"token\":\"",
        "\"password\":\"",
        "\"secret\":\"",
    ] {
        clean = redact_marker_value(&clean, marker);
    }
    if let Some(index) = clean.to_lowercase().find("authorization:") {
        let end = clean[index..]
            .find('\n')
            .map(|offset| index + offset)
            .unwrap_or_else(|| clean.len());
        clean.replace_range(index..end, "Authorization: [REDACTED]");
    }
    if let Some(index) = clean.to_lowercase().find("bearer ") {
        let rest = &clean[index..];
        let tail = rest
            .find(|character: char| character.is_whitespace())
            .map(|offset| index + offset)
            .unwrap_or_else(|| clean.len());
        clean.replace_range(index..tail, "Bearer [REDACTED]");
    }
    clean
}

fn redact_marker_value(text: &str, marker: &str) -> String {
    let lower = text.to_lowercase();
    let marker_lower = marker.to_lowercase();
    let mut output = text.to_string();
    let mut search_from = 0usize;
    while let Some(found) = lower[search_from..].find(&marker_lower) {
        let start = search_from + found + marker.len();
        let end = output[start..]
            .find(|character: char| {
                character.is_whitespace()
                    || matches!(character, '&' | '"' | '\'' | ',' | ';' | ']' | '}')
            })
            .map(|offset| start + offset)
            .unwrap_or_else(|| output.len());
        output.replace_range(start..end, "[REDACTED]");
        search_from = start + "[REDACTED]".len();
        if search_from >= output.len() {
            break;
        }
    }
    output
}

fn rotate_log_if_large(path: &Path, max_bytes: u64, max_rotations: usize) -> Result<(), String> {
    if !path.exists() {
        return Ok(());
    }
    let metadata = fs::metadata(path).map_err(|error| format!("Could not stat log file {}: {error}", path.display()))?;
    if metadata.len() < max_bytes {
        return Ok(());
    }
    for index in (1..=max_rotations).rev() {
        let source = if index == 1 {
            path.to_path_buf()
        } else {
            path.with_extension(format!("log.{}", index - 1))
        };
        let target = path.with_extension(format!("log.{index}"));
        if source.exists() {
            if target.exists() {
                let _ = fs::remove_file(&target);
            }
            fs::rename(&source, &target).map_err(|error| {
                format!(
                    "Could not rotate log file {} to {}: {error}",
                    source.display(),
                    target.display()
                )
            })?;
        }
    }
    Ok(())
}

fn pump_child_output<R: Read>(reader: R, path: PathBuf, stream_name: &str, boot_id: &str) {
    let mut buffered = BufReader::new(reader);
    let mut line = String::new();
    loop {
        line.clear();
        match buffered.read_line(&mut line) {
            Ok(0) => break,
            Ok(_) => {
                let prefix = format!("[{}][{}][{}] ", Local::now().to_rfc3339(), boot_id, stream_name);
                let clean = redact_log_text(line.trim_end_matches(['\r', '\n']));
                let _ = append_line(&path, &(prefix + &clean + "\n"));
            }
            Err(_) => break,
        }
    }
}

fn http_json_request(port: u16, method: &str, path: &str, body: Option<&str>) -> Result<Value, String> {
    let address = format!("127.0.0.1:{port}");
    let mut stream = TcpStream::connect(&address)
        .map_err(|error| format!("Could not connect to {address} for {method} {path}: {error}"))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(2)))
        .map_err(|error| format!("Could not set read timeout for {address}: {error}"))?;
    stream
        .set_write_timeout(Some(Duration::from_secs(2)))
        .map_err(|error| format!("Could not set write timeout for {address}: {error}"))?;
    let body_text = body.unwrap_or("");
    let request = format!(
        "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
        body_text.as_bytes().len(),
        body_text
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|error| format!("Could not write sidecar request {method} {path}: {error}"))?;
    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| format!("Could not read sidecar response {method} {path}: {error}"))?;
    let (head, body_text) = response
        .split_once("\r\n\r\n")
        .ok_or_else(|| format!("Sidecar response for {method} {path} did not include HTTP headers."))?;
    let status_line = head.lines().next().unwrap_or_default();
    let status_code = status_line
        .split_whitespace()
        .nth(1)
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(0);
    if !(200..300).contains(&status_code) {
        return Err(format!(
            "Sidecar request {method} {path} failed with HTTP {status_code}: {body_text}"
        ));
    }
    serde_json::from_str::<Value>(body_text)
        .map_err(|error| format!("Could not decode JSON body for sidecar request {method} {path}: {error}"))
}

fn port_is_available(port: u16) -> bool {
    TcpListener::bind(("127.0.0.1", port)).is_ok()
}

fn exponential_backoff(base: Duration, max: Duration, failures: u32) -> Duration {
    let multiplier = 1u64 << failures.saturating_sub(1).min(6);
    let millis = base.as_millis() as u64 * multiplier;
    Duration::from_millis(millis.min(max.as_millis() as u64))
}

fn process_is_running(pid: u32) -> bool {
    if pid == 0 {
        return false;
    }
    #[cfg(windows)]
    {
        let output = Command::new("tasklist")
            .args(["/FI", &format!("PID eq {pid}"), "/FO", "CSV", "/NH"])
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .output();
        return output
            .ok()
            .and_then(|output| String::from_utf8(output.stdout).ok())
            .map(|stdout| stdout.contains(&format!(",\"{pid}\"")) || stdout.contains(&format!(",{pid}")))
            .unwrap_or(false);
    }
    #[cfg(not(windows))]
    {
        Command::new("kill")
            .args(["-0", &pid.to_string()])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
    }
}

fn terminate_process_tree(pid: u32) -> Result<(), String> {
    #[cfg(windows)]
    {
        let status = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map_err(|error| format!("Could not invoke taskkill for sidecar pid {pid}: {error}"))?;
        if status.success() {
            return Ok(());
        }
        return Err(format!("taskkill failed for sidecar pid {pid} with status {status}."));
    }
    #[cfg(not(windows))]
    {
        let status = Command::new("kill")
            .args(["-TERM", &pid.to_string()])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map_err(|error| format!("Could not send SIGTERM to sidecar pid {pid}: {error}"))?;
        if status.success() {
            return Ok(());
        }
        Err(format!("SIGTERM failed for sidecar pid {pid} with status {status}."))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    struct TestPaths {
        root: PathBuf,
        appdata: PathBuf,
        runtime: PathBuf,
        workspace: PathBuf,
        state_root: PathBuf,
    }

    impl TestPaths {
        fn new(label: &str) -> Self {
            let root = std::env::temp_dir().join(format!(
                "astrabridge-sidecar-supervision-{label}-{}",
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis()
            ));
            let appdata = root.join("appdata");
            let runtime = root.join("runtime");
            let workspace = root.join("workspace");
            let state_root = workspace.join(".astrabridge").join("desktop-sidecar");
            fs::create_dir_all(&appdata).unwrap();
            fs::create_dir_all(&runtime).unwrap();
            fs::create_dir_all(&workspace).unwrap();
            fs::create_dir_all(&state_root).unwrap();
            Self {
                root,
                appdata,
                runtime,
                workspace,
                state_root,
            }
        }
    }

    impl Drop for TestPaths {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    fn test_sidecar_script() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("astrabridge-sidecar")
            .join("sidecar_server.py")
    }

    fn test_config(paths: &TestPaths) -> SidecarLaunchConfig {
        SidecarLaunchConfig {
            sidecar_path: test_sidecar_script(),
            seed_root: paths.workspace.clone(),
            state_root: paths.state_root.clone(),
            build_version: "0.1.0-test".to_string(),
            python_candidates: vec!["python".to_string(), "py".to_string()],
            extra_env: HashMap::from([
                ("ASTRABRIDGE_APPDATA".to_string(), paths.appdata.display().to_string()),
                ("ASTRABRIDGE_RUNTIME_ROOT".to_string(), paths.runtime.display().to_string()),
                ("ASTRABRIDGE_PORT".to_string(), "0".to_string()),
            ]),
            tuning: SidecarSupervisorTuning {
                ready_timeout: Duration::from_secs(20),
                shutdown_timeout: Duration::from_secs(8),
                monitor_poll: Duration::from_millis(300),
                restart_backoff_base: Duration::from_millis(200),
                restart_backoff_max: Duration::from_millis(1_000),
                circuit_window: Duration::from_secs(10),
                circuit_open: Duration::from_secs(2),
                circuit_failure_limit: 2,
            },
        }
    }

    fn wait_until(timeout: Duration, predicate: impl Fn() -> bool) -> bool {
        let deadline = Instant::now() + timeout;
        while Instant::now() < deadline {
            if predicate() {
                return true;
            }
            thread::sleep(Duration::from_millis(150));
        }
        false
    }

    #[test]
    fn redact_log_text_masks_common_secret_markers() {
        let value = redact_log_text(
            "Authorization: Bearer abc123 token=def456 api_key=ghi789 password=secret-value",
        );
        assert!(!value.contains("abc123"));
        assert!(!value.contains("def456"));
        assert!(!value.contains("ghi789"));
        assert!(!value.contains("secret-value"));
        assert!(value.contains("[REDACTED]"));
    }

    #[test]
    fn supervisor_restarts_after_forced_sidecar_exit() {
        let paths = TestPaths::new("restart");
        let supervisor = SidecarSupervisor::new(test_config(&paths)).unwrap();
        let _original_url = supervisor.sidecar_url().unwrap();
        let original = supervisor.binding_for_test().unwrap();
        let _ = terminate_process_tree(original.pid);
        assert!(wait_until(Duration::from_secs(30), || {
            supervisor
                .binding_for_test()
                .map(|binding| binding.boot_id != original.boot_id || binding.pid != original.pid)
                .unwrap_or(false)
        }));
    }

    #[test]
    fn supervisor_opens_circuit_breaker_after_repeated_launch_failures() {
        let paths = TestPaths::new("circuit");
        let mut config = test_config(&paths);
        config.sidecar_path = paths.root.join("missing-sidecar.py");
        let supervisor = SidecarSupervisor::new(config).unwrap();
        let error = supervisor.sidecar_url().unwrap_err();
        assert!(error.contains("circuit") || error.contains("readiness") || error.contains("Could not start"));
    }

    #[test]
    fn supervisor_does_not_kill_unrelated_listener_on_preferred_port() {
        let paths = TestPaths::new("port-owner");
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let occupied_port = listener.local_addr().unwrap().port();
        let config = test_config(&paths);
        let supervisor = SidecarSupervisor::new(config.clone()).unwrap();
        let fake_record = SidecarLaunchRecord {
            schema_version: SIDECAR_LAUNCH_RECORD_SCHEMA_VERSION.to_string(),
            status: "ready".to_string(),
            boot_id: "stale-boot".to_string(),
            pid: std::process::id(),
            listen_host: "127.0.0.1".to_string(),
            listen_port: Some(occupied_port),
            requested_port: occupied_port,
            build_version: config.build_version.clone(),
            runtime_version: Some("3.11".to_string()),
            durable_run_store_schema_version: Some("astrabridge-durable-run-store-v1".to_string()),
            project_schema_version: Some("astrabridge-project-v1".to_string()),
            created_at: Local::now().to_rfc3339(),
            updated_at: Local::now().to_rfc3339(),
            ready_at: Some(Local::now().to_rfc3339()),
            exited_at: None,
            executable: "python".to_string(),
            seed_root: config.seed_root.display().to_string(),
            source_root: None,
            repo_root: None,
            current_source_match: None,
            owner: SidecarLaunchOwner {
                kind: "astrabridge-desktop".to_string(),
                instance_id: "other".to_string(),
                desktop_pid: 99_999,
                seed_root: config.seed_root.display().to_string(),
            },
            log_paths: HashMap::new(),
            startup_restore: None,
            last_error: None,
        };
        supervisor
            .inner
            .write_json_atomic(&config.launch_record_path(), &fake_record)
            .unwrap();

        let _ = supervisor.sidecar_url().unwrap();
        let binding = supervisor.binding_for_test().unwrap();
        assert_ne!(binding.port, occupied_port);
        assert!(listener.local_addr().is_ok());
    }

    #[test]
    fn two_supervisors_share_one_valid_sidecar_without_cross_termination() {
        let paths = TestPaths::new("shared");
        let config = test_config(&paths);
        let supervisor_a = SidecarSupervisor::new(config.clone()).unwrap();
        let url_a = supervisor_a.sidecar_url().unwrap();
        let binding_a = supervisor_a.binding_for_test().unwrap();

        let supervisor_b = SidecarSupervisor::new(config).unwrap();
        let url_b = supervisor_b.sidecar_url().unwrap();
        let binding_b = supervisor_b.binding_for_test().unwrap();

        assert_eq!(url_a, url_b);
        assert_eq!(binding_a.boot_id, binding_b.boot_id);

        drop(supervisor_a);
        assert!(wait_until(Duration::from_secs(8), || {
            supervisor_b
                .binding_for_test()
                .map(|binding| binding.boot_id == binding_b.boot_id)
                .unwrap_or(false)
        }));
        drop(supervisor_b);
        assert!(wait_until(Duration::from_secs(12), || !process_is_running(binding_b.pid)));
    }

    #[test]
    fn twenty_restart_cycles_leave_no_orphan_sidecar_processes() {
        let paths = TestPaths::new("cycles");
        let supervisor = SidecarSupervisor::new(test_config(&paths)).unwrap();
        let mut seen_pids: Vec<u32> = Vec::new();
        for _ in 0..20 {
            let binding = supervisor.binding_for_test().unwrap_or_else(|| {
                supervisor.sidecar_url().unwrap();
                supervisor.binding_for_test().unwrap()
            });
            seen_pids.push(binding.pid);
            let _ = supervisor.inner.request_graceful_shutdown(&binding);
            assert!(wait_until(Duration::from_secs(10), || !process_is_running(binding.pid)));
            {
                let mut state = supervisor
                    .inner
                    .state
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner());
                state.binding = None;
                state.child = None;
                state.start_requested = true;
                state.starting = false;
            }
            supervisor.inner.condvar.notify_all();
            supervisor.sidecar_url().unwrap();
        }
        let final_binding = supervisor.binding_for_test().unwrap();
        seen_pids.push(final_binding.pid);
        drop(supervisor);
        assert!(wait_until(Duration::from_secs(12), || {
            seen_pids.iter().all(|pid| !process_is_running(*pid))
        }));
    }
}
