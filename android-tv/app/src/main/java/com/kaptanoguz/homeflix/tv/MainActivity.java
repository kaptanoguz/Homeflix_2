package com.kaptanoguz.homeflix.tv;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {

    private static final String PREFS = "homeflix_tv";
    private static final String KEY_URL = "server_url";

    private FrameLayout root;
    private WebView web;
    private View customView;
    private WebChromeClient.CustomViewCallback customCallback;
    private WebChromeClient chrome;
    private AlertDialog dialog;
    private String navJs = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);
        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);

        navJs = readAsset("tv-nav.js");
        setupWebView();
        web.loadUrl(currentUrl());
    }

    private void setupWebView() {
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setUserAgentString(s.getUserAgentString() + " HomeflixTV");

        web.setBackgroundColor(Color.BLACK);
        web.setKeepScreenOn(true);
        web.setFocusable(true);
        web.setFocusableInTouchMode(true);
        web.requestFocus();

        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                view.evaluateJavascript(navJs, null);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    showAddressDialog("Sunucuya bağlanılamadı. Adresi kontrol edin ve bilgisayarda "
                            + "Homeflix'in çalıştığından emin olun.");
                }
            }
        });

        chrome = new WebChromeClient() {
            @Override
            public void onShowCustomView(View view, CustomViewCallback callback) {
                if (customView != null) {
                    callback.onCustomViewHidden();
                    return;
                }
                customView = view;
                customCallback = callback;
                web.setVisibility(View.GONE);
                root.addView(view, new FrameLayout.LayoutParams(
                        FrameLayout.LayoutParams.MATCH_PARENT,
                        FrameLayout.LayoutParams.MATCH_PARENT));
            }

            @Override
            public void onHideCustomView() {
                if (customView == null) return;
                root.removeView(customView);
                customView = null;
                web.setVisibility(View.VISIBLE);
                web.requestFocus();
                if (customCallback != null) {
                    customCallback.onCustomViewHidden();
                    customCallback = null;
                }
            }

            @Override
            public Bitmap getDefaultVideoPoster() {
                return Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888);
            }
        };
        web.setWebChromeClient(chrome);
    }

    // ---- Sunucu adresi ----

    private String currentUrl() {
        SharedPreferences p = getSharedPreferences(PREFS, MODE_PRIVATE);
        return p.getString(KEY_URL, BuildConfig.DEFAULT_URL);
    }

    private String normalizeUrl(String raw) {
        String u = raw.trim();
        if (u.isEmpty()) return currentUrl();
        if (!u.contains("://")) u = "http://" + u;
        Uri uri = Uri.parse(u);
        if ("http".equals(uri.getScheme()) && uri.getPort() == -1 && uri.getHost() != null) {
            u = "http://" + uri.getHost() + ":5000" + (uri.getPath() == null ? "" : uri.getPath());
        }
        return u;
    }

    private void showAddressDialog(String message) {
        if (dialog != null && dialog.isShowing()) return;
        final EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setText(currentUrl());
        input.setSelectAllOnFocus(true);

        dialog = new AlertDialog.Builder(this)
                .setTitle("Homeflix sunucu adresi")
                .setMessage(message)
                .setView(input)
                .setPositiveButton("Bağlan", (d, w) -> {
                    String u = normalizeUrl(input.getText().toString());
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_URL, u).apply();
                    web.loadUrl(u);
                })
                .setNegativeButton("İptal", null)
                .show();
    }

    // ---- Tuşlar ----

    private void media(String action) {
        web.evaluateJavascript("window.hfTvMedia && window.hfTvMedia('" + action + "')", null);
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        switch (keyCode) {
            case KeyEvent.KEYCODE_MENU:
                showAddressDialog("Bilgisayarın adresini girin (örn. 192.168.1.50:5000)");
                return true;
            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
                media("toggle");
                return true;
            case KeyEvent.KEYCODE_MEDIA_PLAY:
                media("play");
                return true;
            case KeyEvent.KEYCODE_MEDIA_PAUSE:
                media("pause");
                return true;
            case KeyEvent.KEYCODE_MEDIA_REWIND:
                media("back");
                return true;
            case KeyEvent.KEYCODE_MEDIA_FAST_FORWARD:
                media("fwd");
                return true;
            default:
                break;
        }

        // Tam ekran videoda sayfaya tuş gitmeyebilir; burada doğrudan yönet.
        if (customView != null && event.getRepeatCount() == 0) {
            switch (keyCode) {
                case KeyEvent.KEYCODE_DPAD_CENTER:
                case KeyEvent.KEYCODE_ENTER:
                    media("toggle");
                    return true;
                case KeyEvent.KEYCODE_DPAD_LEFT:
                    media("back");
                    return true;
                case KeyEvent.KEYCODE_DPAD_RIGHT:
                    media("fwd");
                    return true;
                case KeyEvent.KEYCODE_DPAD_UP:
                case KeyEvent.KEYCODE_DPAD_DOWN:
                    return true;
                default:
                    break;
            }
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    public void onBackPressed() {
        if (customView != null) {
            chrome.onHideCustomView();
        } else if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    @Override
    protected void onDestroy() {
        root.removeAllViews();
        web.destroy();
        super.onDestroy();
    }

    private String readAsset(String name) {
        try (InputStream in = getAssets().open(name)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return "";
        }
    }
}
