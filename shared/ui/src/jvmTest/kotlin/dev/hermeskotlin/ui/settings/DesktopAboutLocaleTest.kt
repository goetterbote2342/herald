package dev.hermeskotlin.ui.settings

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.runComposeUiTest
import com.composeunstyled.theme.ColorScheme
import dev.hermeskotlin.core.settings.AppSettings
import dev.hermeskotlin.designsystem.HermesTheme
import dev.hermeskotlin.designsystem.LocalDesktopLayout
import dev.hermeskotlin.ui.ProvideAppLanguage
import dev.hermeskotlin.ui.applyAppLanguage
import java.util.Locale
import kotlin.test.Test

@OptIn(ExperimentalTestApi::class)
class DesktopAboutLocaleTest {
    @Test fun aboutDescriptionFollowsTheAppLanguage() = runComposeUiTest {
        val previous = Locale.getDefault()
        val language = mutableStateOf("es")
        try {
            setContent {
                ProvideAppLanguage(language.value) {
                    HermesTheme(ColorScheme.Light) {
                        CompositionLocalProvider(LocalDesktopLayout provides true) {
                            SettingsView(AppSettings(), GatewayInfo(), "https://fixture.example", {}, {}, {}, {})
                        }
                    }
                }
            }
            onNodeWithText("Un cliente de escritorio para Hermes Agent.").performScrollTo().assertExists()
            runOnIdle { language.value = "en" }
            onNodeWithText("A desktop client for Hermes Agent.").performScrollTo().assertExists()
        } finally {
            applyAppLanguage(null)
            Locale.setDefault(previous)
        }
    }
}
