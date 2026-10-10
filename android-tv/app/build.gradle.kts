plugins {
    id("com.android.application")
}

// Sunucu adresi: gradle assembleDebug -PserverUrl=http://10.1.5.74:5000
val serverUrl: String = (project.findProperty("serverUrl") as String?) ?: "http://10.1.5.74:5000"

android {
    namespace = "com.kaptanoguz.homeflix.tv"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.kaptanoguz.homeflix.tv"
        minSdk = 23
        targetSdk = 34
        versionCode = 2
        versionName = "1.1"
        buildConfigField("String", "DEFAULT_URL", "\"$serverUrl\"")
    }

    // Her derleme aynı anahtarla imzalanır; yoksa GitHub her seferinde yeni anahtar üretir ve yeni sürüm
    // eskisinin üzerine kurulamaz (kaldırınca kayıtlı sunucu adresi de silinir).
    signingConfigs {
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
