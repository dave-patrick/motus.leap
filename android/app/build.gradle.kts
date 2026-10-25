import java.util.Properties

plugins { id("com.android.application") }

// Release signing reads a keystore.properties file kept OUTSIDE the repository.
// Default location: ~/.motus-leap-signing/keystore.properties
// Override with the MOTUS_SIGNING_PROPERTIES environment variable.
// Keys: storeFile, storePassword, keyAlias, keyPassword. Never commit these.
val signingProps = Properties().apply {
    val path = System.getenv("MOTUS_SIGNING_PROPERTIES")
        ?: "${System.getProperty("user.home")}/.motus-leap-signing/keystore.properties"
    val file = File(path)
    if (file.isFile) file.inputStream().use { load(it) }
}

android {
    namespace = "com.motus.leap"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.motus.leap"
        minSdk = 26
        targetSdk = 36
        versionCode = 13
        versionName = "0.5.3"
        testInstrumentationRunner = "com.motus.leap.SessionTestRunner"
    }
    signingConfigs {
        if (signingProps.getProperty("storeFile") != null) {
            create("release") {
                storeFile = file(signingProps.getProperty("storeFile"))
                storePassword = signingProps.getProperty("storePassword")
                keyAlias = signingProps.getProperty("keyAlias")
                keyPassword = signingProps.getProperty("keyPassword")
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
dependencies { implementation("com.google.android.material:material:1.13.0") }
