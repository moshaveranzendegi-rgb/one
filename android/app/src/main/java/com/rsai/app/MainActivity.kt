package com.rsai.app

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable

class MainActivity : Activity() {
    private var webView: WebView? = null
    private var filePathCallback: ValueCallback<Array<Uri>>? = null
    private val filePickerRequest = 2107
    private val prefs by lazy { getSharedPreferences("rs_ai", MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val savedUrl = prefs.getString("server", "") ?: ""
        val savedToken = prefs.getString("token", "") ?: ""
        if (savedUrl.isNotBlank() && savedToken.isNotBlank()) {
            openStudio(savedUrl, savedToken)
        } else {
            showConnectScreen(savedUrl, savedToken)
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun field(hint: String, value: String = "", secret: Boolean = false): EditText {
        val edit = EditText(this)
        edit.hint = hint
        edit.setText(value)
        edit.textSize = 14f
        edit.setPadding(dp(12), dp(9), dp(12), dp(9))
        edit.setTextColor(Color.WHITE)
        edit.setHintTextColor(Color.LTGRAY)
        edit.background = rounded(0xFF17263B.toInt(), 0xFF34465F.toInt())
        if (secret) edit.inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        return edit
    }

    private fun rounded(fill: Int, stroke: Int): GradientDrawable {
        return GradientDrawable().apply {
            setColor(fill)
            cornerRadius = dp(12).toFloat()
            setStroke(dp(1), stroke)
        }
    }

    private fun showConnectScreen(urlValue: String, tokenValue: String) {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(24), dp(28), dp(24), dp(28))
            setBackgroundColor(Color.rgb(11, 18, 32))
        }
        val title = TextView(this).apply {
            text = "RS ai"
            textSize = 30f
            setTextColor(Color.rgb(95, 224, 193))
            typeface = Typeface.DEFAULT_BOLD
        }
        val subtitle = TextView(this).apply {
            text = "اتصال به موتور تولید ویدئو روی رایانهٔ ویندوزی"
            textSize = 15f
            setTextColor(Color.WHITE)
            setPadding(0, dp(6), 0, dp(20))
        }
        val urlInput = field("نشانی رایانه، نمونه: http://192.168.1.20:8765", urlValue)
        urlInput.layoutDirection = View.LAYOUT_DIRECTION_LTR
        val tokenInput = field("محتوای فایل access.token", tokenValue, true)
        tokenInput.layoutDirection = View.LAYOUT_DIRECTION_LTR
        val note = TextView(this).apply {
            text = "موبایل و رایانه باید روی یک شبکهٔ مطمئن باشند. در ویندوز فایل RUN_RS-ai_LAN.bat را اجرا کن و توکن را از مسیر نمایش‌داده‌شده بخوان. این اپ به‌تنهایی مدل سنگین آواتار را روی گوشی اجرا نمی‌کند."
            textSize = 12f
            setTextColor(Color.rgb(165, 182, 203))
            setPadding(0, dp(14), 0, dp(18))
        }
        val connect = Button(this).apply {
            text = "اتصال به RS ai"
            isAllCaps = false
            setTextColor(Color.rgb(7, 34, 29))
            background = rounded(Color.rgb(95, 224, 193), Color.rgb(95, 224, 193))
            setOnClickListener {
                val url = urlInput.text.toString().trim().trimEnd('/')
                val token = tokenInput.text.toString().trim()
                if (!(url.startsWith("http://") || url.startsWith("https://")) || token.length < 24) {
                    AlertDialog.Builder(this@MainActivity).setTitle("اطلاعات ناقص است")
                        .setMessage("نشانی باید با http:// یا https:// آغاز شود و توکن معتبر را وارد کن.")
                        .setPositiveButton("باشه", null).show()
                    return@setOnClickListener
                }
                prefs.edit().putString("server", url).putString("token", token).apply()
                openStudio(url, token)
            }
        }
        root.addView(title)
        root.addView(subtitle)
        root.addView(urlInput, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { bottomMargin = dp(12) })
        root.addView(tokenInput, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(note)
        root.addView(connect, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(52)))
        setContentView(root)
    }

    private fun openStudio(serverUrl: String, token: String) {
        val browser = WebView(this)
        webView = browser
        browser.setBackgroundColor(Color.rgb(11, 18, 32))
        browser.isVerticalScrollBarEnabled = true
        browser.isHorizontalScrollBarEnabled = false
        browser.overScrollMode = View.OVER_SCROLL_IF_CONTENT_SCROLLS
        browser.settings.javaScriptEnabled = true
        browser.settings.domStorageEnabled = true
        browser.settings.allowFileAccess = false
        browser.settings.allowContentAccess = true
        browser.settings.mediaPlaybackRequiresUserGesture = true
        browser.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val host = Uri.parse(serverUrl).host
                val next = request.url
                return next.host != host
            }
        }
        browser.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                this@MainActivity.filePathCallback?.onReceiveValue(null)
                this@MainActivity.filePathCallback = filePathCallback
                val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                    putExtra(Intent.EXTRA_ALLOW_MULTIPLE, false)
                }
                return try {
                    startActivityForResult(Intent.createChooser(intent, "انتخاب فایل برای RS ai"), filePickerRequest)
                    true
                } catch (_: Exception) {
                    this@MainActivity.filePathCallback = null
                    false
                }
            }
        }
        setContentView(browser)
        browser.loadUrl("$serverUrl/#token=${Uri.encode(token)}")
    }

    @Deprecated("Legacy callback required by WebChromeClient file picker on broad Android versions")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == filePickerRequest) {
            val result = if (resultCode == RESULT_OK) {
                val single = data?.data
                if (single != null) arrayOf(single) else data?.clipData?.let { clip -> Array(clip.itemCount) { index -> clip.getItemAt(index).uri } }
            } else null
            filePathCallback?.onReceiveValue(result)
            filePathCallback = null
        }
    }

    @Deprecated("System back button support")
    override fun onBackPressed() {
        val browser = webView
        if (browser != null && browser.canGoBack()) browser.goBack() else super.onBackPressed()
    }
}
