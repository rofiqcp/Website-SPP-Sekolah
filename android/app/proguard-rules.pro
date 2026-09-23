-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

-keep class id.sch.elyaomy.spp.MainActivity { *; }

-keepclassmembers class * {
    public <methods>;
}

-dontwarn android.webkit.**
