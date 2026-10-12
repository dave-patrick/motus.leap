package com.motus.leap;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import java.nio.charset.StandardCharsets;

/** App-private encrypted session; the AES key never leaves Android Keystore. */
final class SessionStore {
    private static final String ALIAS = "motus.session";
    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(ALIAS, null);
    }
    static void save(Context context, ApiClient client) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE, key());
        cipher.updateAAD(client.base.getBytes(StandardCharsets.UTF_8));
        byte[] encrypted = cipher.doFinal(client.sessionToken().getBytes(StandardCharsets.UTF_8));
        context.getSharedPreferences("session", Context.MODE_PRIVATE).edit().putString("server", client.base)
            .putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
            .putString("token", Base64.encodeToString(encrypted, Base64.NO_WRAP)).commit();
    }
    static ApiClient load(Context context) {
        var preferences = context.getSharedPreferences("session", Context.MODE_PRIVATE);
        if (!preferences.contains("token")) return null;
        try {
            ApiClient client = new ApiClient(preferences.getString("server", ""));
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Base64.decode(preferences.getString("iv", ""), Base64.NO_WRAP)));
            cipher.updateAAD(client.base.getBytes(StandardCharsets.UTF_8));
            client.restoreToken(new String(cipher.doFinal(Base64.decode(preferences.getString("token", ""), Base64.NO_WRAP)), StandardCharsets.UTF_8));
            return client;
        } catch (Exception invalid) { clear(context); return null; }
    }
    static void clear(Context context) { context.getSharedPreferences("session", Context.MODE_PRIVATE).edit().clear().commit(); }
}
