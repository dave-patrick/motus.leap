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
    private final String[] pages = {"Scans", "AI sort", "Playlists", "Channels"};

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) {
            googleVerifier = state.getString("googleVerifier");
            googleState = state.getString("googleState");
            googleServer = state.getString("googleServer");
        }
        loginScreen(""); acceptGoogle(getIntent());
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        state.putString("googleVerifier", googleVerifier);
        state.putString("googleState", googleState);
        state.putString("googleServer", googleServer);
    }
    @Override protected void onNewIntent(Intent intent) { super.onNewIntent(intent); setIntent(intent); acceptGoogle(intent); }
    private int dp(int size) { return Math.round(size * getResources().getDisplayMetrics().density); }
    private void frame() {
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
        ImageView logo = new ImageView(this); logo.setImageResource(com.motus.leap.R.drawable.brand_icon);
        logo.setContentDescription("motus.leap logo");
        brand.addView(logo, new LinearLayout.LayoutParams(dp(36), dp(36)));
        TextView name = label(brand, "motus.leap", 21, ink); name.setPadding(dp(10), dp(8), 0, dp(8));
        name.setLayoutParams(new LinearLayout.LayoutParams(0, -2, 1));
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
        LinearLayout form = new LinearLayout(this); form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(0, dp(48), 0, dp(24)); scroll.addView(form);
        ImageView art = new ImageView(this); art.setImageResource(R.drawable.brand_icon);
        art.setContentDescription("motus.leap");
        form.addView(art, new LinearLayout.LayoutParams(dp(104), dp(104)));
        label(form, "Your library,\norganized.", 32, ink);
        label(form, "Scan your YouTube library and find the right playlist for every video.", 16, muted);
        String server = getPreferences(MODE_PRIVATE).getString("server", "https://tubemanager.onrender.com");
        LinearLayout serverPanel = new LinearLayout(this); serverPanel.setOrientation(LinearLayout.VERTICAL);
        EditText address = field(serverPanel, "Server address", server, InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        Button google = button(form, "Continue with Google", () -> startGoogle(address.getText().toString()));
        ((MaterialButton) google).setBackgroundTintList(ColorStateList.valueOf(accent));
        google.setTextColor(Color.rgb(7, 16, 29));
        LinearLayout.LayoutParams googleParams = (LinearLayout.LayoutParams) google.getLayoutParams();
        googleParams.topMargin = dp(28);
        label(form, "Sign in securely with your Google account.", 13, muted);
        if (!message.isEmpty()) label(form, message, 14, Color.rgb(255, 180, 171));
        Button settings = button(form, "Server settings", () -> serverPanel.setVisibility(serverPanel.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE));
        ((MaterialButton) settings).setBackgroundTintList(ColorStateList.valueOf(Color.TRANSPARENT));
        settings.setTextColor(muted);
        form.addView(serverPanel); serverPanel.setVisibility(View.GONE);
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
        int[] icons = {R.drawable.ic_scan, R.drawable.ic_sort, R.drawable.ic_playlist, R.drawable.ic_channel};
        for (int i = 0; i < pages.length; i++) nav.getMenu().add(0, i + 1, i, pages[i]).setIcon(icons[i]);
        nav.setSelectedItemId(java.util.Arrays.asList(pages).indexOf(page) + 1);
        nav.setOnItemSelectedListener(item -> { home(pages[item.getItemId() - 1]); return true; });
        root.addView(nav);
        MaterialButton options = new MaterialButton(this);
        options.setBackgroundTintList(ColorStateList.valueOf(Color.TRANSPARENT));
        options.setElevation(0);
        options.setText("Options"); options.setTextColor(muted); options.setAllCaps(false);
        LinearLayout toolbar = (LinearLayout) root.getChildAt(0);
        toolbar.addView(options, new LinearLayout.LayoutParams(-2, dp(48)));
        options.setOnClickListener(view -> {
            PopupMenu menu = new PopupMenu(this, options);
            menu.getMenu().add("Refresh"); menu.getMenu().add("Server settings"); menu.getMenu().add("Sign out");
            menu.setOnMenuItemClickListener(item -> {
                if (item.getTitle().equals("Refresh")) home(page);
                else if (item.getTitle().equals("Server settings")) open(api.base + "/settings");
                else { ApiClient previous = api; loginScreen(""); network.execute(() -> { try { previous.logout(); } catch (Exception ignored) {} }); }
                return true;
            }); menu.show();
        });
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
                if (error instanceof ApiClient.SessionExpiredException) { loginScreen(error.getMessage()); return; }
                content.removeAllViews(); label(content, readable(error), 16, ink);
                button(content, "Try again", () -> home(page));
            }); }
        });
    }
    private void render(String destination, JSONObject data) {
        if (destination.equals("Scans")) {
            label(content, "Scan your library", 20, ink);
            label(content, "Find duplicates and misplaced videos. Scans keep running on your server.", 15, muted);
            button(content, "Sync playlists", () -> queueScan("sync_playlists"));
            MaterialButton scan = (MaterialButton) button(content, "Full library scan", () -> queueScan("full_cluster_scan"));
            scan.setBackgroundTintList(ColorStateList.valueOf(accent)); scan.setTextColor(Color.rgb(7, 16, 29));
            button(content, "Scan duplicates", () -> queueScan("scan_duplicates"));
            button(content, "Scan misplaced videos", () -> queueScan("scan_misplaced"));
            button(content, "View scan findings", () -> findings());
            label(content, "Library overview", 20, ink);
            row("Playlists", data.optString("total_playlists", "Unavailable"), null);
            row("Videos", data.optString("total_videos", "Unavailable"), null);
            row("Subscriptions", data.optString("total_subscriptions", "Unavailable"), null);
            row("Last scan", data.optString("last_scan", "Never"), null);
            row("Current task", data.isNull("current_task") ? "No task running" : data.optString("current_task"), null);
            row("Queued tasks", data.optString("pending_actions", "Unavailable"), null);
            button(content, "Channel mappings", () -> home("Mappings"));
            button(content, "Open server settings", () -> open(api.base + "/settings"));
            return;
        }
        if (destination.equals("AI sort")) {
            label(content, "Review before you move", 20, ink);
            label(content, "Choose a source playlist, then a video. Your server's AI suggests a destination; you approve each move. Configure the AI provider in server settings first.", 16, muted);
            JSONArray playlists = data.optJSONArray("playlists");
            if (playlists == null || playlists.length() == 0) {
                label(content, "No playlists available. Connect YouTube on your account website, then refresh.", 16, muted); return;
            }
            for (int i = 0; i < playlists.length(); i++) {
                JSONObject playlist = playlists.optJSONObject(i);
                if (playlist != null) button(content, playlist.optString("title", "Untitled playlist"), () -> chooseVideo(playlist, playlists));
            }
            return;
        }
        String key = destination.equals("Playlists") ? "playlists" : destination.equals("Channels") ? "channels" : "mappings";
        JSONArray items = data.optJSONArray(key);
        if (items == null) { label(content, "The server returned an unexpected response. Check that it runs a compatible motus.leap version.", 16, ink); return; }
        if (items.length() == 0) { label(content, "No " + key + " yet. Connect YouTube or organize your library on the website, then refresh.", 16, muted); return; }
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i); if (item == null) continue;
            String id = item.optString("id");
            if (destination.equals("Playlists"))
                row(item.optString("title", "Untitled playlist"), item.optString("video_count", item.optString("item_count", "—")) + " videos", "https://www.youtube.com/playlist?list=" + Uri.encode(id));
            else if (destination.equals("Channels"))
                row(item.optString("title", "Unnamed channel"), item.optString("subscribers", "—") + " subscribers", "https://www.youtube.com/channel/" + Uri.encode(id));
            else row(item.optString("channel", item.optString("channel_id")), "Playlist: " + item.optString("playlist"), null);
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
                if (error instanceof ApiClient.SessionExpiredException) { loginScreen(error.getMessage()); return; }
                content.removeAllViews(); label(content, readable(error), 16, ink);
                button(content, "Back", () -> home(page));
            }); }
        });
    }
    private void queueScan(String action) {
        new AlertDialog.Builder(this).setTitle("Run this scan?")
            .setMessage("This scans your server's connected YouTube library and may use YouTube API quota.")
            .setNegativeButton("Cancel", null).setPositiveButton("Run scan", (dialog, which) ->
                perform("Queuing scan…", client -> client.post("/api/action", new JSONObject().put("action", action)), response -> {
                    label(content, "Scan queued", 22, ink);
                    label(content, "The server accepted the scan. This does not mean it has finished.", 16, muted);
                    button(content, "Check progress", () -> home("Scans"));
                })).show();
    }
    private void findings() {
        perform("Loading scan findings…", client -> client.get("/api/maintenance"), response -> {
            label(content, "Scan findings", 22, ink);
            // Preserve the backend's reported fields rather than inventing counts.
            var keys = response.keys();
            while (keys.hasNext()) {
                String key = keys.next(); Object value = response.opt(key);
                if (value instanceof JSONArray) row(key.replace('_', ' '), ((JSONArray) value).length() + " items", null);
                else if (value != null && value != JSONObject.NULL) row(key.replace('_', ' '), value.toString(), null);
            }
            button(content, "Back to scans", () -> home("Scans"));
        });
    }
    private void chooseVideo(JSONObject source, JSONArray playlists) {
        perform("Loading playlist videos…", client -> client.get("/api/youtube/videos?playlist_id=" + Uri.encode(source.getString("id"))), response -> {
            JSONArray videos = response.optJSONArray("videos");
            label(content, source.optString("title"), 22, ink);
            if (videos == null || videos.length() == 0) label(content, "No videos available in this playlist.", 16, muted);
            else for (int i = 0; i < videos.length(); i++) {
                JSONObject video = videos.optJSONObject(i);
                if (video != null) button(content, video.optString("title", "Untitled video"), () -> suggest(video, source, playlists));
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
            if (!suggestion.isNull("error")) { label(content, suggestion.optString("error"), 16, ink); return; }
            String name = suggestion.optString("matched_playlist", "");
            JSONObject target = null;
            for (int i = 0; i < playlists.length(); i++) {
                JSONObject candidate = playlists.getJSONObject(i);
                if (name.equals(candidate.optString("title"))) {
                    if (target != null) { label(content, "Several playlists share that title. Rename them before sorting.", 16, ink); return; }
                    target = candidate;
                }
            }
            if (target == null) label(content, "The AI could not identify a matching playlist. Nothing was moved.", 16, muted);
            else if (target.optString("id").equals(source.optString("id"))) label(content, "This video already belongs in its current playlist.", 16, muted);
            else {
                JSONObject destination = target;
                label(content, "Suggested playlist: " + name, 18, ink);
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
            button(content, "Back to AI sorting", () -> home("AI sort"));
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
