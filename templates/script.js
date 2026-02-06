function googleTranslateElementInit() {
    new google.translate.TranslateElement({
        pageLanguage: 'en',
        includedLanguages: 'mr,hi,en'
    }, 'google_translate_element');

    // गुगलच्या स्टाईल्स ओव्हरराईड करण्यासाठी इंटरव्हल
    const overrideInterval = setInterval(() => {
        const select = document.querySelector('.goog-te-combo');
        if (select) {
            select.style.setProperty('background-color', '#a8e063', 'important');
            select.style.setProperty('color', '#0b130e', 'important');
            select.style.setProperty('border-radius', '12px', 'important');
            // जर लोगो अजूनही दिसत असेल तर त्याला हाईड करा
            const gadget = document.querySelector('.goog-te-gadget');
            if(gadget) gadget.style.fontSize = "0px";
        }
    }, 500);

    // ५ सेकंदानंतर चेक करणे थांबवा
    setTimeout(() => clearInterval(overrideInterval), 5000);
}