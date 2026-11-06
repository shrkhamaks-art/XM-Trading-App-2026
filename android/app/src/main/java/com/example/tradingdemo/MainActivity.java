package com.example.tradingdemo;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.view.View;
import android.widget.*;
import org.json.JSONObject;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Sandbox-only native client. Does not submit deposits, withdrawals or trading orders. */
public class MainActivity extends Activity {
    private LinearLayout root;
    private TextView message;
    private EditText email, password, otp;
    private String accessToken = "";
    private String loginEmail = "";
    private interface Result { void done(JSONObject json, Exception error); }
    @Override public void onCreate(Bundle state) { super.onCreate(state); showLogin(); }
    private TextView text(String value, int size) {
        TextView t = new TextView(this); t.setText(value); t.setTextColor(Color.WHITE);
        t.setTextSize(size); t.setPadding(0, 12, 0, 12); root.addView(t); return t;
    }
    private void page(String title) {
        ScrollView scroll = new ScrollView(this);
        root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(32, 36, 32, 36); root.setBackgroundColor(Color.rgb(20,20,24));
        scroll.addView(root); setContentView(scroll);
        text(title, 23); text("SANDBOX • لا توجد أموال أو صفقات حقيقية", 14);
        message = text("", 15);
    }
    private EditText field(String hint, boolean secret) {
        EditText e = new EditText(this); e.setHint(hint); e.setHintTextColor(0xffaaaaaa);
        e.setTextColor(Color.WHITE);
        if (secret) e.setInputType(129);
        root.addView(e); return e;
    }
    private void button(String label, Runnable action) {
        Button b = new Button(this); b.setText(label); b.setOnClickListener(v -> action.run()); root.addView(b);
    }
    private void showLogin() {
        page("XM TRADING | تسجيل الدخول");
        email = field("البريد الإلكتروني", false); password = field("كلمة المرور", true);
        button("طلب رمز التحقق", () -> {
            loginEmail = email.getText().toString().trim();
            try { JSONObject body = new JSONObject().put("email", loginEmail).put("password", password.getText().toString());
                api("POST", "/auth/request-otp", body, false, (json, err) -> {
                    if (err != null) message.setText("فشل الطلب: " + err.getMessage());
                    else showOtp();
                });
            } catch(Exception ex) { message.setText(ex.getMessage()); }
        });
        button("فحص الخادم", () -> api("GET", "/health", null, false, (json, err) ->
            message.setText(err == null ? json.toString() : "تعذر الاتصال: " + err.getMessage())));
    }
    private void showOtp() {
        page("التحقق بخطوتين"); otp = field("رمز OTP المكون من 6 أرقام", false);
        button("تأكيد وتسجيل الدخول", () -> {
            try { JSONObject body = new JSONObject().put("email", loginEmail).put("code", otp.getText().toString().trim());
                api("POST", "/auth/verify-otp", body, false, (json, err) -> {
                    if (err != null) message.setText("التحقق فشل: " + err.getMessage());
                    else { accessToken = json.optString("access_token", ""); if (!accessToken.isEmpty()) showDashboard(); }
                });
            } catch(Exception ex) { message.setText(ex.getMessage()); }
        });
        button("العودة", this::showLogin);
    }
    private void showDashboard() {
        page("الحساب التجريبي | لوحة المستثمر");
        button("الملف الشخصي", () -> showResource("/auth/me", "الملف الشخصي"));
        button("الحسابات والأرصدة الدفترية", () -> showResource("/accounts", "الحسابات"));
        button("سجل المعاملات", () -> showResource("/transactions", "المعاملات"));
        button("تسجيل الخروج", () -> api("POST", "/auth/logout", new JSONObject(), true, (json, err) -> {
            accessToken = ""; showLogin();
        }));
    }
    private void showResource(String path, String title) {
        page(title); button("رجوع", this::showDashboard);
        api("GET", path, null, true, (json, err) -> message.setText(err == null ? json.toString() : "خطأ: " + err.getMessage()));
    }
    private void api(String method, String path, JSONObject body, boolean auth, Result callback) {
        String base = BuildConfig.API_BASE_URL;
        if (!base.startsWith("https://")) { callback.done(null, new SecurityException("HTTPS API URL required")); return; }
        new Thread(() -> {
            HttpURLConnection c = null; JSONObject data = null; Exception failure = null;
            try {
                URL u = new URL(base.replaceAll("/+$", "") + path);
                c = (HttpURLConnection)u.openConnection(); c.setConnectTimeout(7000); c.setReadTimeout(7000);
                c.setRequestMethod(method); c.setRequestProperty("Accept", "application/json");
                if (auth) { if (accessToken.isEmpty()) throw new SecurityException("Login required");
                    c.setRequestProperty("Authorization", "Bearer " + accessToken); }
                if (body != null) { c.setDoOutput(true); c.setRequestProperty("Content-Type", "application/json");
                    try(OutputStream out = c.getOutputStream()) { out.write(body.toString().getBytes(StandardCharsets.UTF_8)); } }
                int status = c.getResponseCode();
                InputStream in = status < 400 ? c.getInputStream() : c.getErrorStream();
                ByteArrayOutputStream out = new ByteArrayOutputStream(); byte[] buffer = new byte[2048]; int n;
                if (in != null) try(InputStream input = in) { while((n = input.read(buffer)) != -1) {
                    if (out.size() + n > 65536) throw new IOException("Response too large"); out.write(buffer,0,n); } }
                if (status < 200 || status >= 300) throw new IOException("HTTP " + status);
                data = new JSONObject(out.toString("UTF-8"));
            } catch(Exception ex) { failure = ex; }
            finally { if(c != null) c.disconnect(); }
            JSONObject result = data; Exception error = failure;
            runOnUiThread(() -> callback.done(result, error));
        }).start();
    }
}
