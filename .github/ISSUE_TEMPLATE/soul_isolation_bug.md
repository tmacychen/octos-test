# Bug: Soul Configuration Not Properly Isolated Across Multiple Profiles/Users

## Problem Description

In multi-profile or multi-user scenarios for Telegram/Discord bots, the `/soul` command's personalized prompt configuration (soul) is not properly isolated by profile or chat_id. Different users/profiles share the same soul file, causing later settings to overwrite previous ones.

### Affected Scope
- **Module**: Gateway Dispatcher / Soul Service
- **Commands**: `/soul`, `/soul show`, `/soul reset`, `/soul <text>`
- **Test Cases**: `test_soul_per_profile` (Telegram & Discord)

---

## Reproduction Steps


1. Start gateway (using unified data-dir):
   ```bash
   octos gateway --config config.json --data-dir /tmp/test-octos
   ```

2. User A (chat_id=100) sets soul:
   ```
   /soul You are a helpful assistant for coding.
   ```

3. User B (chat_id=200) sets soul:
   ```
   /soul You are a creative writing tutor.
   ```

4. User A queries soul:
   ```
   /soul
   ```

**Expected:** Returns "You are a helpful assistant for coding."  
**Actual:** Returns "You are a creative writing tutor." ❌

---

## Root Cause Analysis

### Code Path Tracing

1. **Test Startup Parameters** (`test_run.py:855`):
   ```python
   [BINARY_PATH, "gateway", "--config", config_file, "--data-dir", TEST_DIR]
   # TEST_DIR = /tmp/octos_test (shared by all profiles)
   ```

2. **Runtime Initialization** (`gateway_runtime.rs:197, 1397`):
   ```rust
   let data_dir = resolve_data_dir(cmd.data_dir.clone())?;  // /tmp/octos_test
   
   let session_dispatcher = GatewayDispatcher::new(...)
       .with_data_dir(data_dir.clone());  // Globally shared same data_dir
   ```

3. **Soul Read/Write Operations** (`gateway_dispatcher.rs:570, 603`):
   ```rust
   // Read soul
   read_soul(data_dir)  // → {data_dir}/soul.md
   
   // Write soul
   write_soul(data_dir, arg)  // → {data_dir}/soul.md
   ```

4. **Soul Service Implementation** (`soul_service.rs:10-24`):
   ```rust
   const SOUL_FILENAME: &str = "soul.md";
   
   pub fn read_soul(data_dir: &Path) -> Option<String> {
       let path = data_dir.join(SOUL_FILENAME);  // Fixed filename, no isolation
       std::fs::read_to_string(&path)
   }
   
   pub fn write_soul(data_dir: &Path, content: &str) -> io::Result<()> {
       let path = data_dir.join(SOUL_FILENAME);  // Fixed filename, will overwrite
       std::fs::write(&path, content.trim())
   }
   ```

### Core Issue

**Soul Storage Key Design Flaw**: The current implementation stores soul as `{data_dir}/soul.md`, which is a **global singleton file** that cannot distinguish between different:
- Profile IDs
- Channels (telegram/discord)
- Chat IDs / User IDs

When multiple users or profiles are used simultaneously, later write operations directly overwrite previous content.

---

## Solution

### Solution Comparison

| Solution | Isolation Level | Pros | Cons | Recommendation |
|----------|----------------|------|------|----------------|
| **Solution 1: Profile-Level Isolation** | Profile | Aligns with business semantics, consistent with existing architecture | Multiple users within same profile share soul | ⭐⭐⭐⭐⭐ |
| Solution 2: Chat-Level Isolation | Chat/User | Finest granularity isolation | File count explosion, complex management | ⭐⭐⭐ |
| Solution 3: Session Key Isolation | Session | Complete isolation | Over-engineering, doesn't match soul semantics | ⭐⭐ |

### Recommended Solution: Profile-Level Isolation

#### Design Approach

Soul is a **profile-level personalized configuration** and should be stored in the profile's dedicated data directory:

```
{profiles_dir}/{profile_id}/data/soul.md
```

Instead of the current global location:
```
{global_data_dir}/soul.md  ❌
```

#### Implementation Steps

##### 1. Modify `GatewayDispatcher` to Support Dynamic data_dir

**File**: `crates/octos-cli/src/gateway_dispatcher.rs`

Currently `GatewayDispatcher` holds a single `data_dir: Option<PathBuf>`, needs to be changed to dynamically resolve based on message context:

```rust
// New field
pub(crate) profile_store: Option<Arc<ProfileStore>>,

// Modify handle_soul_command
pub async fn handle_soul_command(
    &self,
    cmd: &str,
    reply_channel: &str,
    reply_chat_id: &str,
    profile_id: &str,  // New parameter: extracted from message
) -> Option<DispatchResult> {
    // Resolve exclusive data_dir based on profile_id
    let data_dir = self.resolve_profile_data_dir(profile_id)?;
    
    // ... subsequent logic unchanged
}
```

##### 2. Pass profile_id Through Message Processing Pipeline

**File**: `crates/octos-cli/src/commands/gateway/gateway_runtime.rs`

When calling dispatcher, extract profile_id from inbound message:

```rust
// Current code (around line 1420)
let dispatch_result = session_dispatcher
    .handle_soul_command(&cmd, &channel, &chat_id)
    .await;

// Change to
let profile_id = extract_profile_id_from_message(&msg).unwrap_or(MAIN_PROFILE_ID);
let dispatch_result = session_dispatcher
    .handle_soul_command(&cmd, &channel, &chat_id, profile_id)
    .await;
```

##### 3. Update ProfileStore to Provide Convenience Methods

**File**: `crates/octos-cli/src/profiles.rs`

Ensure `resolve_data_dir` method is publicly accessible:

```rust
impl ProfileStore {
    /// Resolve the data directory for a given profile ID
    pub fn resolve_data_dir_for_id(&self, profile_id: &str) -> Option<PathBuf> {
        self.get(profile_id).ok().flatten()
            .map(|profile| self.resolve_data_dir(&profile))
    }
}
```

##### 4. Adjust Test Configuration

**File**: `test_run.py`

Ensure test environment correctly configures profile isolation:

```python
# Current configuration lacks profile definitions, need to add
config = {
    "version": 1,
    "provider": "anthropic",
    "model": "MiniMax-M2.7",
    "api_key_env": "ANTHROPIC_API_KEY",
    "base_url": "https://api.minimaxi.com/anthropic",
    "gateway": {
        "channels": [...],
    },
    # Add profiles configuration to support isolation testing
    "profiles": [
        {"id": "profile-a", "name": "Profile A"},
        {"id": "profile-b", "name": "Profile B"},
    ]
}
```

---

## Solution Approach

### Root Cause
Soul configuration is stored as a global singleton file (`{data_dir}/soul.md`), causing different profiles/users to overwrite each other's settings.

### Fix Strategy: Profile-Level Isolation

Store soul in profile-specific data directories instead of the global location:
```
Current:  {global_data_dir}/soul.md          ❌ (shared by all)
Fixed:    {profiles_dir}/{profile_id}/data/soul.md  ✅ (isolated per profile)
```

### Implementation Outline

1. **Modify `GatewayDispatcher`** - Add `profile_store` field and update `handle_soul_command` to accept `profile_id` parameter, then resolve profile-specific data directory dynamically.

2. **Update Message Pipeline** - Extract `profile_id` from inbound messages in `gateway_runtime.rs` and pass it to the dispatcher when handling soul commands.

3. **Add ProfileStore Helper** - Implement `resolve_data_dir_for_id()` method to get the correct data directory for any profile ID.

4. **Adjust Test Config** - Ensure test configurations define multiple profiles to properly validate isolation.

This approach aligns with the existing profile architecture and ensures soul configurations are properly isolated across different profiles.
