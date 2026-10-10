package com.kaptanoguz.homeflix.tv;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.KeyEvent;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.TextView;

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
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable retry = () -> load(currentUrl());
    private TextView offlineView;
    private boolean offline;
    private boolean loadFailed;

    private static final int RETRY_MS = 5000;
    private static final String ADDRESS_HINT = "Bilgisayarın adresini girin (örn. 10.1.5.74:5000)";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);
        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        offlineView = new TextView(this);
        offlineView.setBackgroundColor(Color.parseColor("#0b0b0f"));
        offlineView.setTextColor(Color.parseColor("#f5f5f7"));
        offlineView.setTextSize(20);
        offlineView.setGravity(Gravity.CENTER);
        offlineView.setPadding(48, 0, 48, 0);
        offlineView.setVisibility(View.GONE);
        // Telefonda kumanda yok: bağlantı ekranına dokunmak adres penceresini açar.
        offlineView.setOnClickListener(v -> showAddressDialog(ADDRESS_HINT));
        root.addView(offlineView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);

        navJs = readAsset("tv-nav.js");
        setupWebView();
        // Adres yalnızca ilk açılışta sorulur; sonra kayıtlı adres kullanılır.
        if (hasSavedUrl()) load(currentUrl());
        else showAddressDialog("Homeflix'in çalıştığı bilgisayarın adresini girin. Bir kez sorulur, sonra hatırlanır.");
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
                // Homeflix menü ve oynatıcıyı açarken geçmişe kayıt ekler (history.pushState) ve WebView bunu da
                // sayfa yüklendi diye bildirir; bu yüzden burada geçmiş silinmemeli, yoksa X / geri oku çalışmaz.
                if (loadFailed) return;
                hideOffline();
                view.evaluateJavascript(navJs, null);  // tv-nav.js kendini bir kez kurar
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    loadFailed = true;
                    showOffline();
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

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS, MODE_PRIVATE);
    }

    private boolean hasSavedUrl() {
        return prefs().contains(KEY_URL);
    }

    private String currentUrl() {
        return prefs().getString(KEY_URL, BuildConfig.DEFAULT_URL);
    }

    private void load(String url) {
        handler.removeCallbacks(retry);
        loadFailed = false;
        web.loadUrl(url);
    }

    // Bilgisayar uykuda ya da sunucu yeniden başlıyor olabilir: adresi yeniden sormak yerine kayıtlı adresi
    // sessizce tekrar dener. Mesaj WebView'in üstünde ayrı bir katmanda durur, tarayıcı geçmişine girmez.
    // Bu ekranda OK / MENU tuşu ya da ekrana dokunmak adres penceresini açar.
    private void showOffline() {
        offline = true;
        String host = Uri.parse(currentUrl()).getAuthority();
        offlineView.setText("HOMEFLIX\n\n" + host + " adresine bağlanılamıyor.\n"
                + "Bilgisayar açık mı? 5 saniye içinde tekrar denenecek.\n\n"
                + "Adresi değiştirmek için OK tuşuna basın ya da ekrana dokunun.");
        offlineView.setVisibility(View.VISIBLE);
        handler.removeCallbacks(retry);
        handler.postDelayed(retry, RETRY_MS);
    }

    private void hideOffline() {
        if (!offline) return;
        offline = false;
        offlineView.setVisibility(View.GONE);
        web.requestFocus();
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
        input.setText(currentUrl().replaceFirst("^http://", ""));
        input.setSelectAllOnFocus(true);
        handler.removeCallbacks(retry);

        dialog = new AlertDialog.Builder(this)
                .setTitle("Homeflix sunucu adresi")
                .setMessage(message)
                .setView(input)
                .setPositiveButton("Bağlan", (d, w) -> {
                    String u = normalizeUrl(input.getText().toString());
                    prefs().edit().putString(KEY_URL, u).apply();
                    load(u);
                })
                .setNegativeButton("İptal", (d, w) -> load(currentUrl()))
                .setOnCancelListener(d -> load(currentUrl()))
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
                showAddressDialog(ADDRESS_HINT);
                return true;
            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER:
                if (offline) {
                    showAddressDialog(ADDRESS_HINT);
                    return true;
                }
                break;
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
        if (offline) {
            super.onBackPressed();
        } else if (customView != null) {
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
        handler.removeCallbacks(retry);
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
