.class public Lcom/obsmainnet/app/MainActivity;
.super Landroid/app/Activity;

.field private static final HOME_URL:Ljava/lang/String; = "https://app.obsmainnet.us.ci"
.field private static final FILE_REQUEST:I = 0x539
.field mUploadCallback:Landroid/webkit/ValueCallback;
.field private mWebView:Landroid/webkit/WebView;

.method public constructor <init>()V
    .registers 1
    invoke-direct {p0}, Landroid/app/Activity;-><init>()V
    return-void
.end method

.method protected onCreate(Landroid/os/Bundle;)V
    .registers 5
    .param p1, "savedInstanceState"    # Landroid/os/Bundle;

    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V

    new-instance v0, Landroid/webkit/WebView;
    invoke-direct {v0, p0}, Landroid/webkit/WebView;-><init>(Landroid/content/Context;)V
    iput-object v0, p0, Lcom/obsmainnet/app/MainActivity;->mWebView:Landroid/webkit/WebView;

    invoke-virtual {v0}, Landroid/webkit/WebView;->getSettings()Landroid/webkit/WebSettings;
    move-result-object v1

    const/4 v2, 0x1
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setJavaScriptEnabled(Z)V
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setDomStorageEnabled(Z)V
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setDatabaseEnabled(Z)V
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setJavaScriptCanOpenWindowsAutomatically(Z)V
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setSupportZoom(Z)V
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setBuiltInZoomControls(Z)V
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setUseWideViewPort(Z)V
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setLoadWithOverviewMode(Z)V

    const/4 v2, 0x0
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setDisplayZoomControls(Z)V
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setMediaPlaybackRequiresUserGesture(Z)V

    const/16 v2, -0x1
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setCacheMode(I)V

    new-instance v1, Landroid/webkit/WebViewClient;
    invoke-direct {v1}, Landroid/webkit/WebViewClient;-><init>()V
    invoke-virtual {v0, v1}, Landroid/webkit/WebView;->setWebViewClient(Landroid/webkit/WebViewClient;)V

    new-instance v1, Lcom/obsmainnet/app/MainActivity$UploadClient;
    invoke-direct {v1, p0}, Lcom/obsmainnet/app/MainActivity$UploadClient;-><init>(Lcom/obsmainnet/app/MainActivity;)V
    invoke-virtual {v0, v1}, Landroid/webkit/WebView;->setWebChromeClient(Landroid/webkit/WebChromeClient;)V

    if-eqz p1, :load_home
    invoke-virtual {v0, p1}, Landroid/webkit/WebView;->restoreState(Landroid/os/Bundle;)Landroid/webkit/WebBackForwardList;
    goto :show

    :load_home
    sget-object v1, Lcom/obsmainnet/app/MainActivity;->HOME_URL:Ljava/lang/String;
    invoke-virtual {v0, v1}, Landroid/webkit/WebView;->loadUrl(Ljava/lang/String;)V

    :show
    invoke-virtual {p0, v0}, Landroid/app/Activity;->setContentView(Landroid/view/View;)V
    return-void
.end method

.method protected onSaveInstanceState(Landroid/os/Bundle;)V
    .registers 3
    .param p1, "outState"    # Landroid/os/Bundle;

    invoke-super {p0, p1}, Landroid/app/Activity;->onSaveInstanceState(Landroid/os/Bundle;)V
    iget-object v0, p0, Lcom/obsmainnet/app/MainActivity;->mWebView:Landroid/webkit/WebView;
    if-eqz v0, :end
    invoke-virtual {v0, p1}, Landroid/webkit/WebView;->saveState(Landroid/os/Bundle;)Landroid/os/Bundle;

    :end
    return-void
.end method

.method public onBackPressed()V
    .registers 2

    iget-object v0, p0, Lcom/obsmainnet/app/MainActivity;->mWebView:Landroid/webkit/WebView;
    if-eqz v0, :fallback
    invoke-virtual {v0}, Landroid/webkit/WebView;->canGoBack()Z
    move-result v1
    if-eqz v1, :fallback
    invoke-virtual {v0}, Landroid/webkit/WebView;->goBack()V
    return-void

    :fallback
    invoke-super {p0}, Landroid/app/Activity;->onBackPressed()V
    return-void
.end method

.method protected onActivityResult(IILandroid/content/Intent;)V
    .registers 12
    .param p1, "requestCode"    # I
    .param p2, "resultCode"    # I
    .param p3, "data"    # Landroid/content/Intent;

    const/16 v0, 0x539
    if-ne p1, v0, :default

    iget-object v0, p0, Lcom/obsmainnet/app/MainActivity;->mUploadCallback:Landroid/webkit/ValueCallback;
    const/4 v1, 0x0
    iput-object v1, p0, Lcom/obsmainnet/app/MainActivity;->mUploadCallback:Landroid/webkit/ValueCallback;
    if-eqz v0, :default

    const/4 v2, 0x0
    const/4 v3, -0x1
    if-ne p2, v3, :deliver
    if-eqz p3, :deliver

    invoke-virtual {p3}, Landroid/content/Intent;->getClipData()Landroid/content/ClipData;
    move-result-object v4
    if-eqz v4, :single

    invoke-virtual {v4}, Landroid/content/ClipData;->getItemCount()I
    move-result v5
    if-lez v5, :single

    new-array v2, v5, [Landroid/net/Uri;
    const/4 v3, 0x0

    :loop
    if-ge v3, v5, :deliver
    invoke-virtual {v4, v3}, Landroid/content/ClipData;->getItemAt(I)Landroid/content/ClipData$Item;
    move-result-object v6
    invoke-virtual {v6}, Landroid/content/ClipData$Item;->getUri()Landroid/net/Uri;
    move-result-object v7
    aput-object v7, v2, v3
    add-int/lit8 v3, v3, 0x1
    goto :loop

    :single
    invoke-virtual {p3}, Landroid/content/Intent;->getData()Landroid/net/Uri;
    move-result-object v4
    if-eqz v4, :deliver
    const/4 v5, 0x1
    new-array v2, v5, [Landroid/net/Uri;
    const/4 v5, 0x0
    aput-object v4, v2, v5

    :deliver
    invoke-interface {v0, v2}, Landroid/webkit/ValueCallback;->onReceiveValue(Ljava/lang/Object;)V
    return-void

    :default
    invoke-super {p0, p1, p2, p3}, Landroid/app/Activity;->onActivityResult(IILandroid/content/Intent;)V
    return-void
.end method
