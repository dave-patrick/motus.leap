package com.motus.leap;

import org.json.JSONObject;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;

/** Native client for the existing FastAPI contracts. */
final class ApiClient {
    final String base;
    private String token = "";
    String sessionToken() { return token; }
    void restoreToken(String saved) { token = saved; }
    ApiClient(String address) {
        URI uri = URI.create(address.trim());
        if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                || uri.getRawUserInfo() != null || uri.getRawQuery() != null || uri.getRawFragment() != null)
            throw new IllegalArgumentException("Enter an HTTPS server address without credentials or query parameters.");
        base = address.trim().replaceAll("/+$", "");
    }
    JSONObject get(String path) throws Exception { return request(path, null); }
    JSONObject post(String path, JSONObject body) throws Exception { return request(path, body); }
    void exchangeGoogle(String code, String verifier) throws Exception {
        token = post("/api/auth/mobile/exchange", new JSONObject().put("code", code)
            .put("code_verifier", verifier)).getString("access_token");
    }
    void logout() throws Exception {
        try { request("/api/auth/logout", new JSONObject()); } finally { token = ""; }
    }
    private JSONObject request(String path, JSONObject body) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) URI.create(base + path).toURL().openConnection();
        try {
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(45000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("Accept", "application/json");
            if (!token.isEmpty()) connection.setRequestProperty("Authorization", "Bearer " + token);
            if (body != null) {
                connection.setRequestMethod("POST");
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json");
                try (var stream = connection.getOutputStream()) {
                    stream.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
            }
            int status = connection.getResponseCode();
            InputStream raw = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            String text = "";
            if (raw != null) try (InputStream stream = raw) {
                ByteArrayOutputStream buffer = new ByteArrayOutputStream();
                byte[] chunk = new byte[4096];
                int count;
                while ((count = stream.read(chunk)) != -1) buffer.write(chunk, 0, count);
                text = new String(buffer.toByteArray(), StandardCharsets.UTF_8);
            }
            if (status == 401) throw new SessionExpiredException();
            if (status < 200 || status >= 300) {
                String detail = "Server returned " + status + ". Please retry or check your account.";
                if (status >= 400 && status < 500) {
                    try { Object message = new JSONObject(text).opt("detail"); if (message instanceof String) detail = (String) message; }
                    catch (Exception ignored) {}
                }
                throw new Exception(detail);
            }
            JSONObject response = new JSONObject(text);
            if (!response.isNull("error") && !response.optString("error").isEmpty())
                throw new Exception(response.optString("error"));
            return response;
        } finally { connection.disconnect(); }
    }
    static final class SessionExpiredException extends Exception {
        SessionExpiredException() { super("Sign-in failed or your session expired. Please sign in again."); }
    }
}
