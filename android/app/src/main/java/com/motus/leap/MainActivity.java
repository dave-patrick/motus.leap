package com.motus.leap;

import androidx.appcompat.app.AppCompatActivity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.view.WindowInsets;
import android.widget.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.security.SecureRandom;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import android.util.Base64;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.google.android.material.textfield.TextInputLayout;
import com.google.android.material.textfield.TextInputEditText;

/** Native Android screens backed by motus.leap's server. */
public final class MainActivity extends AppCompatActivity {
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private final int ink = Color.rgb(243, 245, 248), muted = Color.rgb(184, 192, 204);
    private final int accent = Color.rgb(155, 203, 255), surface = Color.rgb(17, 21, 28);
    private LinearLayout root, content;
    private ApiClient api;
    private String googleVerifier, googleState, googleServer;
    private int generation;
    private String page = "Scans";
    private String scanAction = "", previousJob = "", resultsFilter = "All";
    private final String[] pages = {"Scans", "AI sort", "Playlists", "Channels", "Settings"};
    private final android.os.Handler refresh = new android.os.Handler(android.os.Looper.getMainLooper());

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        scanAction = getPreferences(MODE_PRIVATE).getString("scanAction", "");
        previousJob = getPreferences(MODE_PRIVATE).getString("previousJob", "");
        resultsFilter = getPreferences(MODE_PRIVATE).getString("resultsFilter", "All");
        if (state != null) {
            googleVerifier = state.getString("googleVerifier");
            googleState = state.getString("googleState");
            googleServer = state.getString("googleServer");
        }
        api = SessionStore.load(this);
        if (api == null) loginScreen(""); else home("Scans");
        acceptGoogle(getIntent());
    }
    @Override protected void onStop() { super.onStop(); refresh.removeCallbacksAndMessages(null); }
    @Override protected void onResume() { super.onResume(); if (api != null && page.equals("Scan status")) scanStatus(); }
    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        state.putString("googleVerifier", googleVerifier);
        state.putString("googleState", googleState);
        state.putString("googleServer", googleServer);
    }
    @Override protected void onNewIntent(Intent intent) { super.onNewIntent(intent); setIntent(intent); acceptGoogle(intent); }
    private int dp(int size) { return Math.round(size * getResources().getDisplayMetrics().density); }
    private void frame() {
        refresh.removeCallbacksAndMessages(null);
        generation++;
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(9, 11, 16));
        root.setPadding(dp(20), dp(12), dp(20), dp(12));
        if (android.os.Build.VERSION.SDK_INT >= 30) root.setOnApplyWindowInsetsListener((view, insets) -> {
            var bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
            view.setPadding(dp(20) + bars.left, dp(12) + bars.top, dp(20) + bars.right, dp(12) + bars.bottom);
            return insets;
        });
        setContentView(root);
        // getInsets(Type) is API 30; older Android uses its platform inset handling.
        if (android.os.Build.VERSION.SDK_INT < 30) {
            root.setOnApplyWindowInsetsListener(null);
            root.setFitsSystemWindows(true);
        }
        root.requestApplyInsets();
        LinearLayout brand = new LinearLayout(this); brand.setGravity(android.view.Gravity.CENTER_VERTICAL);
        root.addView(brand);
        brand.addView(brandedHeader(57), new LinearLayout.LayoutParams(0, dp(68), 1));
    }
    private LinearLayout brandedHeader(int iconSize) {
        LinearLayout brand = new LinearLayout(this); brand.setGravity(android.view.Gravity.CENTER_VERTICAL);
        ImageView symbol = new ImageView(this); symbol.setImageResource(R.drawable.brand_symbol);
        symbol.setScaleType(ImageView.ScaleType.FIT_CENTER); symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        brand.addView(symbol, new LinearLayout.LayoutParams(dp(iconSize), dp(iconSize)));
        View name = new WordmarkView(this, 36);
        LinearLayout.LayoutParams textParams = new LinearLayout.LayoutParams(0, dp(iconSize), 1); textParams.leftMargin = dp(8);
        brand.addView(name, textParams); return brand;
    }
    private ImageView wordmark() {
        ImageView image = new ImageView(this);
        android.graphics.Bitmap artwork = android.graphics.BitmapFactory.decodeResource(getResources(), R.drawable.brand_wordmark);
        // Display the existing emblem and wordmark, excluding the surrounding banner canvas.
        image.setImageBitmap(android.graphics.Bitmap.createBitmap(artwork, 110, 210, 980, 240));
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setContentDescription("motus.leap");
        return image;
    }
    private TextView label(LinearLayout parent, String text, int size, int color) {
        TextView label = new TextView(this);
        label.setText(text); label.setTextSize(size); label.setTextColor(color);
        label.setPadding(0, dp(size >= 20 ? 16 : 4), 0, dp(8));
        label.setLineSpacing(dp(2), 1.08f);
        if (size >= 18) label.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        parent.addView(label);
        return label;
    }
    private Button button(LinearLayout parent, String text, Runnable action) {
        MaterialButton button = new MaterialButton(this); button.setText(text); button.setAllCaps(false);
        button.setTextSize(14); button.setCornerRadius(dp(16));
        button.setBackgroundTintList(ColorStateList.valueOf(Color.rgb(28, 34, 44)));
        button.setTextColor(ink); button.setElevation(0); button.setMinHeight(dp(52));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, dp(4), 0, dp(4)); parent.addView(button, params);
        button.setOnClickListener(view -> action.run()); return button;
    }
    private EditText field(LinearLayout parent, String title, String value, int type) {
        TextInputLayout box = new TextInputLayout(this);
        box.setBoxBackgroundMode(TextInputLayout.BOX_BACKGROUND_OUTLINE); box.setHint(title);
        box.setBoxCornerRadii(dp(16), dp(16), dp(16), dp(16));
        TextInputEditText input = new TextInputEditText(box.getContext()); input.setText(value); input.setTextColor(ink);
        input.setInputType(type); input.setSingleLine(true); input.setMinHeight(dp(48));
        box.addView(input); LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, dp(8), 0, dp(8)); parent.addView(box, params); return input;
    }
    private void loginScreen(String message) {
        api = null; frame();
        root.removeViewAt(0);
        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout viewport = new LinearLayout(this);
        viewport.setOrientation(LinearLayout.VERTICAL);
        viewport.setGravity(android.view.Gravity.CENTER);
        viewport.setPadding(0, dp(32), 0, dp(32));
        scroll.addView(viewport, new ScrollView.LayoutParams(-1, -1));
        LinearLayout form = new LinearLayout(this); form.setOrientation(LinearLayout.VERTICAL);
        int available = getResources().getDisplayMetrics().widthPixels - dp(40);
        viewport.addView(form, new LinearLayout.LayoutParams(Math.min(dp(420), available), -2));
        ImageView symbol = new ImageView(this); symbol.setImageResource(R.drawable.brand_symbol);
        symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        LinearLayout.LayoutParams symbolParams = new LinearLayout.LayoutParams(dp(144), dp(144));
        symbolParams.gravity = android.view.Gravity.CENTER_HORIZONTAL; form.addView(symbol, symbolParams);
        View wordmark = new WordmarkView(this, 52);
        LinearLayout.LayoutParams brandParams = new LinearLayout.LayoutParams(-1, dp(76)); brandParams.bottomMargin = dp(32);
        form.addView(wordmark, brandParams);
        TextView headline = label(form, "Your library, organized.", 30, ink);
        headline.setPadding(0, 0, 0, dp(12));
        TextView description = label(form, "Scan your YouTube library and find the right playlist for every video.", 16, muted);
        description.setPadding(0, 0, 0, dp(32));
        String server = getPreferences(MODE_PRIVATE).getString("server", "https://tubemanager.onrender.com");
        LinearLayout serverPanel = new LinearLayout(this); serverPanel.setOrientation(LinearLayout.VERTICAL);
        EditText address = field(serverPanel, "Server address", server, InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        android.widget.ImageButton google = new android.widget.ImageButton(this);
        google.setImageResource(R.drawable.google_signin);
        google.setContentDescription("Sign in with Google");
        google.setScaleType(ImageView.ScaleType.FIT_CENTER);
        google.setBackgroundColor(Color.TRANSPARENT); google.setPadding(0, 0, 0, 0);
        LinearLayout.LayoutParams googleParams = new LinearLayout.LayoutParams(Math.min(dp(280), available), dp(56));
        googleParams.bottomMargin = dp(12);
        form.addView(google, googleParams);
        google.setOnClickListener(view -> startGoogle(address.getText().toString()));
        label(form, "Sign in securely with your Google account.", 14, muted);
        if (!message.isEmpty()) {
            TextView error = label(form, message, 14, Color.rgb(255, 180, 171));
            error.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        }
        View divider = new View(this); divider.setBackgroundColor(Color.rgb(42, 47, 58));
        LinearLayout.LayoutParams dividerParams = new LinearLayout.LayoutParams(-1, dp(1));
        dividerParams.setMargins(0, dp(28), 0, dp(12)); form.addView(divider, dividerParams);
        Button settings = button(form, "Server settings", () -> serverPanel.setVisibility(serverPanel.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE));
        ((MaterialButton) settings).setBackgroundTintList(ColorStateList.valueOf(Color.TRANSPARENT));
        settings.setTextColor(muted); settings.setGravity(android.view.Gravity.START | android.view.Gravity.CENTER_VERTICAL);
        settings.setPadding(0, 0, 0, 0);
        settings.setContentDescription("Server settings. Change the server address if you use a different server.");
        form.addView(serverPanel); serverPanel.setVisibility(View.GONE);
        // Use the actual inset/window width, including split-screen and rotation.
        viewport.addOnLayoutChangeListener((view, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) -> {
            int width = Math.min(dp(420), Math.max(1, right - left - view.getPaddingLeft() - view.getPaddingRight()));
            if (form.getLayoutParams().width != width) {
                form.getLayoutParams().width = width; form.requestLayout();
                google.getLayoutParams().width = Math.min(dp(280), width); google.requestLayout();
            }
        });
    }

    private void home(String destination) {
        page = destination; frame();
        label(root, page, 22, ink);
        ScrollView scroll = new ScrollView(this);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        content = new LinearLayout(this); content.setOrientation(LinearLayout.VERTICAL); scroll.addView(content);
        BottomNavigationView nav = new BottomNavigationView(this);
        nav.setBackgroundColor(surface);
        nav.setItemActiveIndicatorColor(ColorStateList.valueOf(Color.rgb(37, 53, 74)));
        int[] icons = {R.drawable.ic_scan, R.drawable.ic_sort, R.drawable.ic_playlist, R.drawable.ic_channel, R.drawable.ic_settings};
        for (int i = 0; i < pages.length; i++) nav.getMenu().add(0, i + 1, i, pages[i]).setIcon(icons[i]);
        nav.setLabelVisibilityMode(com.google.android.material.navigation.NavigationBarView.LABEL_VISIBILITY_LABELED);
        nav.setItemHorizontalTranslationEnabled(false);
        nav.setSelectedItemId(Math.max(1, java.util.Arrays.asList(pages).indexOf(page) + 1));
        nav.setOnItemSelectedListener(item -> { home(pages[item.getItemId() - 1]); return true; });
        root.addView(nav);
        if (destination.equals("Settings")) { settingsScreen(); return; }
        if (destination.equals("Scan status")) { loadScanStatus(); return; }
        label(content, "Loading…", 16, muted);
        ApiClient client = api;
        int requestGeneration = generation;
        String path = destination.equals("Scans") ? "/api/stats" : (destination.equals("Playlists") || destination.equals("AI sort"))
            ? "/api/playlists" : destination.equals("Channels") ? "/api/subscriptions" : "/api/mappings";
        network.execute(() -> {
            try {
                JSONObject data = client.get(path);
                runOnUiThread(() -> {
                    if (isDestroyed() || requestGeneration != generation) return;
                    content.removeAllViews(); render(destination, data);
                });
            } catch (Exception error) { runOnUiThread(() -> {
                if (isDestroyed() || requestGeneration != generation) return;
                if (error instanceof ApiClient.SessionExpiredException) { SessionStore.clear(this); loginScreen(error.getMessage()); return; }
                content.removeAllViews(); label(content, readable(error), 16, ink);
                button(content, "Try again", () -> home(page));
            }); }
        });
    }
    private void render(String destination, JSONObject data) {
        if (destination.equals("Scans")) {
            button(content, "Scan status & results", this::scanStatus);
            label(content, "Scan your library", 20, ink);
            label(content, "Find duplicates and misplaced videos. Scans keep running on your server.", 15, muted);
            button(content, "Sync playlists", () -> queueScan("sync_playlists"));
            MaterialButton scan = (MaterialButton) button(content, "Full library scan", () -> queueScan("full_cluster_scan"));
            scan.setBackgroundTintList(ColorStateList.valueOf(accent)); scan.setTextColor(Color.rgb(7, 16, 29));
            button(content, "Scan duplicates", () -> queueScan("scan_duplicates"));
            button(content, "Scan misplaced videos", () -> queueScan("scan_misplaced"));
            button(content, "Scan deleted videos", () -> { resultsFilter = "Deleted"; queueScan("sync_playlists"); });
            button(content, "View scan findings", () -> findings());
            button(content, "Move Watch Later to 1~Sort", () -> moveWatchLater());
            label(content, "Library overview", 20, ink);
            row("Playlists", data.optString("total_playlists", "Unavailable"), null);
            row("Videos", data.optString("total_videos", "Unavailable"), null);
            row("Subscriptions", data.optString("total_subscriptions", "Unavailable"), null);
            row("Last scan", data.optString("last_scan", "Never"), null);
            row("Current task", data.isNull("current_task") ? "No task running" : data.optString("current_task"), null);
            row("Queued tasks", data.optString("pending_actions", "Unavailable"), null);
            button(content, "Channel mappings", () -> home("Mappings"));

            return;
        }
        if (destination.equals("AI sort")) {
            label(content, "Review before you move", 20, ink);
            label(content, "Choose a source playlist, then a video. Your server's AI suggests a destination; you approve each move. Configure the AI provider in server settings first.", 16, muted);
            JSONArray playlists = data.optJSONArray("playlists");
            if (playlists == null || playlists.length() == 0) {
                label(content, "No playlists available. Connect YouTube on your account website, then refresh.", 16, muted); return;
            }
            java.util.List<View> choices = searchChoices(content, "Search playlists");
            for (int i = 0; i < playlists.length(); i++) {
                JSONObject playlist = playlists.optJSONObject(i);
                if (playlist != null) {
                    Button choice = button(content, playlist.optString("title", "Untitled playlist"), () -> chooseVideo(playlist, playlists));
                    choice.setTag(playlist.optString("title")); choices.add(choice);
                }
            }
            return;
        }
        String key = destination.equals("Playlists") ? "playlists" : destination.equals("Channels") ? "channels" : "mappings";
        JSONArray items = data.optJSONArray(key);
        if (items == null) { label(content, "The server returned an unexpected response. Check that it runs a compatible motus.leap version.", 16, ink); return; }
        if (items.length() == 0) { label(content, "No " + key + " yet. Connect YouTube or organize your library on the website, then refresh.", 16, muted); return; }
        java.util.List<View> choices = searchChoices(content, "Search " + key);
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i); if (item == null) continue;
            String id = item.optString("id");
            if (destination.equals("Playlists"))
                row(item.optString("title", "Untitled playlist"), item.optString("video_count", item.optString("item_count", "—")) + " videos", "https://www.youtube.com/playlist?list=" + Uri.encode(id));
            else if (destination.equals("Channels"))
                row(item.optString("title", "Unnamed channel"), item.optString("subscribers", "—") + " subscribers", "https://www.youtube.com/channel/" + Uri.encode(id));
            else row(item.optString("channel", item.optString("channel_id")), "Playlist: " + item.optString("playlist"), null);
            View entry = content.getChildAt(content.getChildCount() - 1);
            entry.setTag(item.optString("title", item.optString("channel", item.optString("channel_id"))) + " " + item.optString("playlist")); choices.add(entry);
        }
    }
    private interface ServerWork { JSONObject run(ApiClient client) throws Exception; }
    private interface ResultWork { void show(JSONObject result) throws Exception; }
    private void perform(String message, ServerWork work, ResultWork result) {
        ApiClient client = api;
        int requestGeneration = generation;
        content.removeAllViews(); label(content, message, 16, muted);
        network.execute(() -> {
            try {
                JSONObject response = work.run(client);
                runOnUiThread(() -> {
                    if (isDestroyed() || requestGeneration != generation) return;
                    content.removeAllViews();
                    try { result.show(response); }
                    catch (Exception error) { label(content, readable(error), 16, ink); button(content, "Back", () -> home(page)); }
                });
            } catch (Exception error) { runOnUiThread(() -> {
                if (isDestroyed() || requestGeneration != generation) return;
                if (error instanceof ApiClient.SessionExpiredException) { SessionStore.clear(this); loginScreen(error.getMessage()); return; }
                content.removeAllViews(); label(content, readable(error), 16, ink);
                button(content, "Back", () -> home(page));
            }); }
        });
    }
    private void settingsScreen() {
        label(content, "Account", 20, ink);
        label(content, "Your Google session stays signed in until it expires or you sign out.", 15, muted);
        row("Connected server", api.base, null);
        button(content, "Server settings", () -> open(api.base + "/settings"));
        button(content, "Refresh library", () -> home("Scans"));
        button(content, "Sign out", () -> {
            ApiClient previous = api; SessionStore.clear(this); loginScreen("");
            network.execute(() -> { try { previous.logout(); } catch (Exception ignored) {} });
        });
    }
    private void scanStatus() { home("Scan status"); }
    private void loadScanStatus() {
        ApiClient client = api; int requestGeneration = generation;
        label(content, "Checking server status…", 16, muted);
        network.execute(() -> {
            try {
                JSONObject stats = client.get("/api/stats");
                runOnUiThread(() -> {
                    if (isDestroyed() || requestGeneration != generation || !page.equals("Scan status")) return;
                    content.removeAllViews();
                    JSONObject job = stats.optJSONObject("job_progress");
                    boolean running = stats.optInt("running_tasks") > 0;
                    boolean queued = stats.optInt("pending_actions") > 0;
                    String state = running ? "running" : queued ? "queued" : job == null ? "idle" : job.optString("state", "idle");
                    if (job != null && !scanAction.isEmpty() && scanAction.equals(job.optString("action"))
                            && !previousJob.equals(job.optString("job_id")) && state.equals("completed")) {
                        scanAction = ""; getPreferences(MODE_PRIVATE).edit().remove("scanAction").apply();
                        findings(); return;
                    }
                    row("Server status", state.replace('_', ' '), null);
                    if (running || queued) {
                        ProgressBar activity = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
                        int total = !running || job == null || !job.optString("state").equals("running") ? 0 : job.optInt("total");
                        activity.setIndeterminate(total <= 0);
                        if (total > 0) { activity.setMax(total); activity.setProgress(job.optInt("completed")); }
                        content.addView(activity, new LinearLayout.LayoutParams(-1, dp(8)));
                    }
                    if (job != null) {
                        label(content, job.optString("message", ""), 16, ink);
                        if (job.optInt("total") > 0) row("Items processed", job.optInt("completed") + " / " + job.optInt("total"), null);
                        JSONArray failures = job.optJSONArray("failures");
                        if (failures != null) for (int i=0; i<failures.length(); i++) label(content, failures.optString(i), 14, Color.rgb(255,180,171));
                    }
                    row("Current task", stats.isNull("current_task") ? "No task running" : stats.optString("current_task"), null);
                    row("Queued tasks", stats.optString("pending_actions", "Unavailable"), null);
                    row("Last completed scan", stats.optString("last_scan", "Never"), null);
                    label(content, "Status refreshes every 5 seconds. Results show the latest available scan; they may belong to an earlier scan while work is running.", 14, muted);
                    button(content, "View scan results", this::findings);
                    button(content, "Refresh now", this::scanStatus);
                    refresh.postDelayed(() -> {
                        if (!isDestroyed() && requestGeneration == generation && page.equals("Scan status")) {
                            content.removeAllViews(); loadScanStatus();
                        }
                    }, 5000);
                });
            } catch (Exception error) { runOnUiThread(() -> {
                if (isDestroyed() || requestGeneration != generation) return;
                content.removeAllViews();
                if (error instanceof ApiClient.SessionExpiredException) { SessionStore.clear(this); loginScreen(readable(error)); return; }
                label(content, readable(error), 16, ink); button(content, "Retry status", this::scanStatus);
            }); }
        });
    }
    private void queueScan(String action) {
        new AlertDialog.Builder(this).setTitle("Run this scan?")
            .setMessage("This scans your server's connected YouTube library and may use YouTube API quota.")
            .setNegativeButton("Cancel", null).setPositiveButton("Run scan", (dialog, which) -> {
                home("Scan status");
                perform("Queuing scan…", client -> {
                    JSONObject stats = client.get("/api/stats"); JSONObject job = stats.optJSONObject("job_progress");
                    return client.post("/api/action", new JSONObject().put("action", action))
                        .put("previous_job", job == null ? "" : job.optString("job_id"));
                }, response -> {
                    scanAction = action; previousJob = response.optString("previous_job");
                    if (action.equals("scan_duplicates")) resultsFilter = "Duplicates";
                    else if (!action.equals("sync_playlists")) resultsFilter = "All";
                    getPreferences(MODE_PRIVATE).edit().putString("scanAction", scanAction).putString("previousJob", previousJob)
                        .putString("resultsFilter", resultsFilter).apply();
                    scanStatus();
                });
            }).show();
    }
    private void findings() {
        page = "Scan results"; refresh.removeCallbacksAndMessages(null);
        perform("Loading scan findings…", client -> client.get("/api/maintenance"), response -> {
            label(content, "Scan findings", 22, ink);
            button(content, "All findings", () -> { resultsFilter = "All"; findings(); });
            button(content, "Duplicates", () -> { resultsFilter = "Duplicates"; findings(); });
            button(content, "Deleted videos", () -> { resultsFilter = "Deleted"; findings(); });
            if (!response.optString("info").isEmpty()) label(content, response.optString("info"), 15, muted);
            label(content, "Review the source and destination below. Approve a move, choose another playlist, or keep the video where it is.", 16, muted);
            if (!resultsFilter.equals("Deleted")) findingGroup("Duplicates", response.optJSONArray("duplicated_videos"));
            if (resultsFilter.equals("All")) {
                findingGroup("Suggested moves", response.optJSONArray("misplaced_videos"));
                findingGroup("Other suggested moves", response.optJSONArray("move_from_x_to_y"));
            }
            if (!resultsFilter.equals("Duplicates")) {
                row("Deleted videos", response.optString("deleted_count", "Not reported"), null);
                if (response.optInt("deleted_count") > 0) button(content, "Remove deleted videos from playlists", this::removeDeleted);
            }
            button(content, "Back to scan status", this::scanStatus);
            button(content, "Back to scans", () -> home("Scans"));
        });
    }
    private void duplicateControls(JSONObject item, String videoId) {
        JSONArray copies = item.optJSONArray("copies");
        if (copies == null || copies.length() == 0) copies = item.optJSONArray("playlists");
        if (copies != null) for (int i=0; i<copies.length(); i++) {
            JSONObject copy = copies.optJSONObject(i); if (copy == null) continue;
            String playlistId = copy.optString("playlist_id", copy.optString("id"));
            String playlistTitle = copy.optString("playlist_title", copy.optString("title", playlistId));
            String copyVideo = copy.optString("video_id", videoId), itemId = copy.optString("playlist_item_id");
            if (playlistId.isEmpty()) continue;
            button(content, "Remove copy from " + playlistTitle, () -> new AlertDialog.Builder(this)
                .setTitle("Remove this playlist copy?")
                .setMessage(item.optString("video_title", item.optString("title", videoId)) + "\n\nRemove only the selected copy from " + playlistTitle + ". Other copies are retained. The video itself stays on YouTube.")
                .setNegativeButton("Cancel", null).setPositiveButton("Remove copy", (dialog, which) ->
                    perform("Removing selected copy…", client -> client.post("/api/maintenance/action", new JSONObject()
                        .put("action", "remove").put("type", "dup").put("video_id", copyVideo)
                        .put("playlist_id", playlistId).put("playlist_item_id", itemId.isEmpty() ? JSONObject.NULL : itemId)), this::maintenanceResult)).show());
        }
        button(content, "Keep these copies · dismiss finding", () -> perform("Dismissing finding…", client ->
            client.post("/api/maintenance/action", new JSONObject().put("action", "keep").put("type", "dup").put("video_id", videoId)), this::maintenanceResult));
    }
    private void removeDeleted() {
        new AlertDialog.Builder(this).setTitle("Remove deleted video entries?")
            .setMessage("Remove deleted or unavailable video entries from your connected playlists using the last synced data. This changes your playlists and uses YouTube API quota.")
            .setNegativeButton("Cancel", null).setPositiveButton("Remove entries", (dialog, which) ->
                perform("Removing deleted video entries…", client -> client.post("/api/maintenance/remove-deleted", new JSONObject()), this::maintenanceResult)).show();
    }
    private void maintenanceResult(JSONObject result) {
        String status = result.optString("status", "unknown");
        label(content, status.equals("success") || status.equals("ok") ? "Action completed" : "Action needs attention", 22, ink);
        label(content, result.optString("message", status.equals("success") || status.equals("ok") ? "The server confirmed the selected action." : "Server status: " + status), 16, ink);
        if (result.has("removed_count")) row("Entries removed", result.optString("removed_count"), null);
        JSONArray errors = result.optJSONArray("errors");
        if (errors != null) for (int i=0; i<errors.length(); i++) label(content, errors.optString(i), 14, Color.rgb(255,180,171));
        button(content, "Return to results", this::findings);
        button(content, "Scan status", this::scanStatus);
    }
    private void moveWatchLater() {
        new AlertDialog.Builder(this).setTitle("Move all Watch Later to 1~Sort?")
            .setMessage("This moves your current Watch Later videos into 1~Sort. Each video is saved in 1~Sort before it is removed from Watch Later. A connected YouTube session is required.")
            .setNegativeButton("Cancel", null).setPositiveButton("Move all", (dialog, which) ->
                perform("Queuing Watch Later move…", client -> client.post("/api/bulk/watch-later-to-sort", new JSONObject().put("confirm", true)), response -> {
                    label(content, "Watch Later move queued", 22, ink);
                    label(content, "The server is reading Watch Later and moving videos. Check progress for completed and failed items.", 16, muted);
                    String operation = response.getString("operation_id");
                    button(content, "Check progress", () -> operationStatus(operation));
                })).show();
    }
    private void findingGroup(String title, JSONArray items) {
        label(content, title + " (" + (items == null ? 0 : items.length()) + ")", 20, ink);
        if (items == null || items.length() == 0) { label(content, "No " + title.toLowerCase() + " reported.", 15, muted); return; }
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i); if (item == null) continue;
            String from = item.optString("current_playlist_title", item.optString("source_playlist_title", "Current playlist"));
            String to = item.optString("mapped_playlist_title", item.optString("target_playlist_title", "Review destination"));
            String reason = item.optString("match_reason", item.optString("channel_title", "Review the suggested destination."));
            String detail = from + " → " + to + "\n" + reason;
            if (title.equals("Duplicates")) {
                StringBuilder locations = new StringBuilder(); JSONArray playlists = item.optJSONArray("playlists");
                if (playlists != null) for (int j=0; j<playlists.length(); j++) {
                    JSONObject playlist = playlists.optJSONObject(j);
                    if (locations.length() > 0) locations.append("\n");
                    locations.append(playlist == null ? playlists.optString(j) : playlist.optString("title", playlist.optString("id")));
                }
                detail = item.optInt("copy_count", playlists == null ? 0 : playlists.length()) + " copies\n" + locations;
            }
            String videoId = item.optString("video_id", item.optString("id"));
            row(item.optString("title", item.optString("video_title", "Untitled video")), detail,
                videoId.isEmpty() ? null : "https://www.youtube.com/watch?v=" + Uri.encode(videoId));
            if (title.equals("Duplicates") && !videoId.isEmpty()) duplicateControls(item, videoId);
            else if (!videoId.isEmpty()) suggestedMoveControls(item, videoId, title.equals("Other suggested moves") ? "move" : "misplaced");
        }
    }
    private void suggestedMoveControls(JSONObject item, String videoId, String type) {
        String sourceId = item.optString("current_playlist_id", item.optString("source_playlist_id"));
        String targetId = item.optString("mapped_playlist_id", item.optString("target_playlist_id"));
        JSONObject video = new JSONObject(), source = new JSONObject(), target = new JSONObject();
        try {
            video.put("video_id", videoId).put("title", item.optString("video_title", item.optString("title", videoId)));
            source.put("id", sourceId).put("title", item.optString("current_playlist_title", item.optString("source_playlist_title", sourceId)));
            target.put("id", targetId).put("title", item.optString("mapped_playlist_title", item.optString("target_playlist_title", targetId)));
        } catch (Exception error) { label(content, readable(error), 14, muted); return; }
        if (!sourceId.isEmpty()) {
            if (!targetId.isEmpty() && !targetId.equals(sourceId))
                button(content, "Approve suggested move", () -> confirmFindingMove(video, source, target));
            button(content, "Choose another destination", () -> chooseFindingDestination(video, source));
        } else label(content, "This finding has no source playlist ID. Run a fresh scan to review its move.", 14, muted);
        button(content, "Keep here · dismiss suggestion", () -> perform("Dismissing suggestion…", client ->
            client.post("/api/maintenance/action", new JSONObject().put("action", "keep").put("type", type)
                .put("video_id", videoId)), this::maintenanceResult));
    }
    private void confirmFindingMove(JSONObject video, JSONObject source, JSONObject target) {
        new AlertDialog.Builder(this).setTitle("Approve this move?")
            .setMessage(video.optString("title") + "\n\nFrom: " + source.optString("title") + "\nTo: " + target.optString("title") + "\n\nThis changes your YouTube playlists.")
            .setNegativeButton("Cancel", null).setPositiveButton("Move video", (dialog, which) -> moveVideo(video, source, target)).show();
    }
    private void chooseFindingDestination(JSONObject video, JSONObject source) {
        perform("Loading destination playlists…", client -> client.get("/api/playlists"), response -> {
            label(content, "Choose a destination", 22, ink);
            label(content, video.optString("title") + "\nFrom: " + source.optString("title"), 16, muted);
            java.util.List<View> choices = searchChoices(content, "Search destination playlists");
            JSONArray playlists = response.optJSONArray("playlists"); int count = 0;
            if (playlists != null) for (int i=0; i<playlists.length(); i++) {
                JSONObject target = playlists.optJSONObject(i);
                if (target == null || target.optString("id").isEmpty() || target.optString("id").equals(source.optString("id"))) continue;
                Button choice = button(content, target.optString("title", target.optString("id")), () -> confirmFindingMove(video, source, target));
                choice.setTag(target.optString("title")); choices.add(choice); count++;
            }
            if (count == 0) label(content, "No other destination playlists are available.", 16, muted);
            button(content, "Back to findings", this::findings);
        });
    }
    private java.util.List<View> searchChoices(LinearLayout parent, String hint) {
        java.util.List<View> choices = new java.util.ArrayList<>();
        EditText search = field(parent, hint, "", InputType.TYPE_CLASS_TEXT);
        search.addTextChangedListener(new android.text.TextWatcher() {
            public void beforeTextChanged(CharSequence text, int start, int count, int after) {}
            public void onTextChanged(CharSequence text, int start, int before, int count) {
                String query = text.toString().toLowerCase(java.util.Locale.ROOT).trim();
                for (View item : choices) item.setVisibility(String.valueOf(item.getTag()).toLowerCase(java.util.Locale.ROOT).contains(query) ? View.VISIBLE : View.GONE);
            }
            public void afterTextChanged(android.text.Editable text) {}
        });
        return choices;
    }
    private void suggestionRecovery(JSONObject video, JSONObject source, JSONArray playlists) {
        button(content, "Try suggestion again", () -> suggest(video, source, playlists));
        button(content, "Choose another video", () -> chooseVideo(source, playlists));
    }
    private void chooseVideo(JSONObject source, JSONArray playlists) {
        perform("Loading playlist videos…", client -> client.get("/api/youtube/videos?playlist_id=" + Uri.encode(source.getString("id"))), response -> {
            JSONArray videos = response.optJSONArray("videos");
            label(content, source.optString("title"), 22, ink);
            if (videos == null || videos.length() == 0) label(content, "No videos available in this playlist.", 16, muted);
            java.util.List<View> choices = searchChoices(content, "Search videos");
            for (int i = 0; videos != null && i < videos.length(); i++) {
                JSONObject video = videos.optJSONObject(i);
                if (video != null) {
                    Button choice = button(content, video.optString("title", "Untitled video"), () -> suggest(video, source, playlists));
                    choice.setTag(video.optString("title")); choices.add(choice);
                }
            }
            button(content, "Choose another playlist", () -> home("AI sort"));
        });
    }
    private void suggest(JSONObject video, JSONObject source, JSONArray playlists) {
        perform("Asking your server's AI for a destination…", client -> {
            String id = video.getString("video_id");
            JSONObject meta = new JSONObject().put("video_id", id).put("title", video.optString("title"))
                .put("channel", video.optString("channel_title", video.optString("channel")))
                .put("description", video.optString("description"));
            return client.post("/api/ai/classify", new JSONObject().put("video_ids", new JSONArray().put(id))
                .put("metadata", new JSONArray().put(meta)));
        }, response -> {
            JSONObject suggestion = response.getJSONArray("results").getJSONObject(0);
            label(content, video.optString("title"), 22, ink);
            if (!suggestion.isNull("error")) { label(content, suggestion.optString("error"), 16, ink); suggestionRecovery(video, source, playlists); return; }
            String name = suggestion.optString("matched_playlist", "");
            JSONObject target = null;
            for (int i = 0; i < playlists.length(); i++) {
                JSONObject candidate = playlists.getJSONObject(i);
                if (name.equals(candidate.optString("title"))) {
                    if (target != null) { label(content, "Several playlists share that title. Rename them before sorting.", 16, ink); suggestionRecovery(video, source, playlists); return; }
                    target = candidate;
                }
            }
            if (target == null) label(content, "The AI could not identify a matching playlist. Nothing was moved.", 16, muted);
            else if (target.optString("id").equals(source.optString("id"))) label(content, "This video already belongs in its current playlist.", 16, muted);
            else {
                JSONObject destination = target;
                label(content, "Suggested playlist: " + name, 18, ink);
                if (!suggestion.optString("reason").isEmpty()) label(content, suggestion.optString("reason"), 16, muted);
                button(content, "Review move", () -> new AlertDialog.Builder(this).setTitle("Move this video?")
                    .setMessage("Move “" + video.optString("title") + "” from “" + source.optString("title") + "” to “" + name + "”? This changes your YouTube playlists.")
                    .setNegativeButton("Cancel", null).setPositiveButton("Move video", (dialog, which) -> moveVideo(video, source, destination)).show());
            }
            button(content, "Choose another video", () -> chooseVideo(source, playlists));
        });
    }
    private void moveVideo(JSONObject video, JSONObject source, JSONObject target) {
        perform("Submitting move…", client -> client.post("/api/bulk/move", new JSONObject()
            .put("video_ids", new JSONArray().put(video.getString("video_id")))
            .put("source_playlist_id", source.getString("id")).put("target_playlist_id", target.getString("id"))), response -> {
                String operation = response.getString("operation_id");
                label(content, "Move submitted", 22, ink);
                label(content, "The server is processing your move.", 16, muted);
                button(content, "Check move result", () -> operationStatus(operation));
            });
    }
    private void operationStatus(String id) {
        perform("Checking move…", client -> client.get("/api/bulk/operations/" + Uri.encode(id)), response -> {
            row("Move status", response.optString("status"), null);
            row("Succeeded", response.optString("succeeded"), null);
            row("Failed", response.optString("failed"), null);
            JSONArray errors = response.optJSONArray("errors");
            if (errors != null) for (int i = 0; i < errors.length(); i++) label(content, errors.optString(i), 16, ink);
            button(content, "Refresh result", () -> operationStatus(id));
            if (page.equals("Scan results")) button(content, "Back to findings", this::findings);
            else button(content, "Back to " + page, () -> home(page));
        });
    }
    private void row(String title, String detail, String url) {
        LinearLayout group = new LinearLayout(this); group.setOrientation(LinearLayout.VERTICAL);
        group.setPadding(dp(16), dp(8), dp(16), dp(8));
        GradientDrawable background = new GradientDrawable(); background.setColor(surface); background.setCornerRadius(dp(16));
        group.setBackground(background);
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, -2); layout.setMargins(0, dp(4), 0, dp(4));
        content.addView(group, layout);
        label(group, title, 18, ink); label(group, detail, 14, muted);
        if (url != null) button(group, "Open in YouTube", () -> open(url));
    }
    private void open(String url) {
        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
        catch (android.content.ActivityNotFoundException error) { Toast.makeText(this, "No browser is available.", Toast.LENGTH_LONG).show(); }
    }
    private String randomKey() {
        byte[] random = new byte[32]; new SecureRandom().nextBytes(random);
        return Base64.encodeToString(random, Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP);
    }
    private void startGoogle(String address) {
        ApiClient client;
        try { client = new ApiClient(address); }
        catch (Exception error) { loginScreen(readable(error)); return; }
        googleVerifier = randomKey(); googleState = randomKey(); googleServer = client.base;
        final String verifier = googleVerifier, clientState = googleState;
        int requestGeneration = generation;
        network.execute(() -> {
            try {
                String challenge = Base64.encodeToString(MessageDigest.getInstance("SHA-256")
                    .digest(verifier.getBytes(StandardCharsets.US_ASCII)), Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP);
                JSONObject response = client.get("/api/auth/mobile/google?code_challenge=" + Uri.encode(challenge) + "&client_state=" + Uri.encode(clientState));
                String url = response.getString("auth_url");
                Uri authorization = Uri.parse(url);
                if (!"https".equals(authorization.getScheme()) || !"accounts.google.com".equals(authorization.getHost()))
                    throw new Exception("The server returned an invalid Google sign-in address.");
                runOnUiThread(() -> { if (!isDestroyed() && requestGeneration == generation) open(url); });
            } catch (Exception error) { runOnUiThread(() -> {
                if (!isDestroyed() && requestGeneration == generation) {
                    googleVerifier = null; googleState = null; googleServer = null;
                    loginScreen(readable(error));
                }
            }); }
        });
    }
    private void acceptGoogle(Intent intent) {
        Uri uri = intent.getData();
        if (uri == null || !"motusleap".equals(uri.getScheme()) || !"oauth".equals(uri.getHost()) || !"/callback".equals(uri.getPath())) return;
        intent.setData(null);
        String code = uri.getQueryParameter("code"), state = uri.getQueryParameter("state");
        if (googleState == null || !googleState.equals(state) || googleVerifier == null || googleServer == null || code == null) {
            loginScreen("This sign-in attempt expired. Tap Continue with Google to start again."); return;
        }
        ApiClient client = new ApiClient(googleServer);
        String verifier = googleVerifier;
        googleState = null; googleVerifier = null; googleServer = null;
        frame(); label(root, "Completing Google sign-in…", 18, ink);
        int requestGeneration = generation;
        network.execute(() -> {
            try {
                client.exchangeGoogle(code, verifier);
                client.get("/api/auth/me");
                SessionStore.save(this, client);
                runOnUiThread(() -> {
                    if (isDestroyed() || requestGeneration != generation) return;
                    api = client; getPreferences(MODE_PRIVATE).edit().putString("server", client.base).apply(); home("Scans");
                });
            } catch (Exception error) { runOnUiThread(() -> {
                if (!isDestroyed() && requestGeneration == generation) loginScreen(readable(error));
            }); }
        });
    }
    private String readable(Exception error) {
        if (error instanceof java.io.IOException) return "Cannot reach your server. Check your connection and try again.";
        return error.getMessage() == null ? "Unable to load data. Please retry." : error.getMessage();
    }
    @Override protected void onDestroy() { generation++; network.shutdownNow(); super.onDestroy(); }
}

