plugins {
    id("com.android.application")
}

// Sunucu adresi: gradle assembleDebug -PserverUrl=http://192.168.1.50:5000
val serverUrl: String = (project.findProperty("serverUrl") as String?) ?: "http://192.168.1.100:5000"

android {
    namespace = "com.kaptanoguz.homeflix.tv"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.kaptanoguz.homeflix.tv"
        minSdk = 23
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
        buildConfigField("String", "DEFAULT_URL", "\"$serverUrl\"")
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
