plugins { id("com.android.application") }
android {
    namespace = "com.motus.leap"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.motus.leap"
        minSdk = 26
        targetSdk = 36
        versionCode = 11
        versionName = "0.5.1"
        testInstrumentationRunner = "com.motus.leap.SessionTestRunner"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
dependencies { implementation("com.google.android.material:material:1.13.0") }
