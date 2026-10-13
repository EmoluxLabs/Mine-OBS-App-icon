.class public Lcom/obsmainnet/app/MainActivity$UploadClient;
.super Landroid/webkit/WebChromeClient;

.field private mActivity:Lcom/obsmainnet/app/MainActivity;

.method public constructor <init>(Lcom/obsmainnet/app/MainActivity;)V
    .registers 2

    invoke-direct {p0}, Landroid/webkit/WebChromeClient;-><init>()V
    iput-object p1, p0, Lcom/obsmainnet/app/MainActivity$UploadClient;->mActivity:Lcom/obsmainnet/app/MainActivity;
    return-void
.end method

.method public onShowFileChooser(Landroid/webkit/WebView;[Landroid/net/Uri;Landroid/webkit/WebChromeClient$FileChooserParams;)Z
    .registers 8
    .param p1, "webView"    # Landroid/webkit/WebView;
    .param p2, "filePathCallback"    # [Landroid/net/Uri;
    .param p3, "fileChooserParams"    # Landroid/webkit/WebChromeClient$FileChooserParams;

    iget-object v0, p0, Lcom/obsmainnet/app/MainActivity$UploadClient;->mActivity:Lcom/obsmainnet/app/MainActivity;

    new-instance v1, Landroid/content/Intent;
    const-string v2, "android.intent.action.GET_CONTENT"
    invoke-direct {v1, v2}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V

    const-string v2, "android.intent.category.OPENABLE"
    invoke-virtual {v1, v2}, Landroid/content/Intent;->addCategory(Ljava/lang/String;)Landroid/content/Intent;

    const-string v2, "*/*"
    invoke-virtual {v1, v2}, Landroid/content/Intent;->setType(Ljava/lang/String;)Landroid/content/Intent;

    const-string v2, "android.intent.extra.ALLOW_MULTIPLE"
    const/4 v3, 0x1
    invoke-virtual {v1, v2, v3}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Z)Landroid/content/Intent;

    iput-object p2, v0, Lcom/obsmainnet/app/MainActivity;->mUploadCallback:Landroid/webkit/ValueCallback;

    const/16 v2, 0x539
    invoke-virtual {v0, v1, v2}, Landroid/app/Activity;->startActivityForResult(Landroid/content/Intent;I)V

    const/4 v2, 0x1
    return v2
.end method
