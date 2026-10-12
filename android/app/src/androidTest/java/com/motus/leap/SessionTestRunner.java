package com.motus.leap;

import android.app.Instrumentation;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.SharedPreferences;
import android.os.Bundle;

/** Device checks use a separate preference file and never touch the user's session. */
public final class SessionTestRunner extends Instrumentation {
    @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }
    @Override public void onStart() {
        Bundle result = new Bundle();
        Context isolated = new ContextWrapper(getTargetContext()) {
            @Override public SharedPreferences getSharedPreferences(String name, int mode) {
                return super.getSharedPreferences("test_" + name, mode);
            }
        };
        try {
            SessionStore.clear(isolated);
            ApiClient client = new ApiClient("https://example.com"); client.restoreToken("test-session-value");
            SessionStore.save(isolated, client);
            ApiClient restored = SessionStore.load(isolated);
            if (restored == null || !restored.sessionToken().equals("test-session-value")) throw new AssertionError("Restore failed");
            if (isolated.getSharedPreferences("session", 0).getString("token", "").contains("test-session-value")) throw new AssertionError("Plaintext stored");
            isolated.getSharedPreferences("session", 0).edit().putString("server", "https://different.example.com").commit();
            if (SessionStore.load(isolated) != null) throw new AssertionError("Server binding failed");
            SessionStore.save(isolated, client);
            isolated.getSharedPreferences("session", 0).edit().putString("token", "tampered").commit();
            if (SessionStore.load(isolated) != null) throw new AssertionError("Tampered session accepted");
            SessionStore.save(isolated, client); SessionStore.clear(isolated);
            if (SessionStore.load(isolated) != null) throw new AssertionError("Sign out failed");
            result.putString("session_checks", "PASS: restore, encrypted storage, server binding, tamper rejection, sign out");
            finish(-1, result);
        } catch (Throwable error) {
            result.putString("session_checks", "FAIL: " + error.getClass().getSimpleName()); finish(0, result);
        } finally { SessionStore.clear(isolated); }
    }
}
