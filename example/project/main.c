// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"

/*---------------------------------------------------------------------------*/
int main () { // This program will run first. POS Interface configuration will be called, and ready to work.
    screenClear ();
    initDatabase ();
    screenAdjust ();
    return 0;
}

void switchHub () {
    screenClear ();
    char text[140];
    char text1[140];
    char text2[140];
    if ( Session.user.role == 0 )
        strcpy (text1, "Manager");
    else if ( Session.user.role == 1 )
        strcpy (text1, "Marketing");
    else if ( Session.user.role == 2 )
        strcpy (text1, "Sale");
    sprintf (text, "Login as %s %c. (%s)", Session.user.firstname, Session.user.lastname[0], text1);

    bannerInverse (Setting.storeName, Setting.storeAddress, "", text);
    for ( int i = 0; i < 7; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("What do you want to do ?");
    bannerBlankBorder ();
    bannerBlankBorder ();
    //These choice will be removed, when the program detects the permission level.
    if ( Session.user.role == 0 ) { // Manager
        bannerBlankBorderTextCen ("1. Go to POS System");
        bannerBlankBorderTextCen ("2. Inventory management");
        bannerBlankBorderTextCen ("3. Customer management");
        bannerBlankBorderTextCen ("4. Personnel management");
        bannerBlankBorderTextCen ("5. Promotion management");
        bannerBlankBorderTextCen ("6. Sales Forecasting");
        bannerBlankBorderTextCen ("7. View Report");
        bannerBlankBorderTextCen ("8. Settings");
        for ( int i = 10; i > 0; i-- )
            bannerBlankBorder ();
    } else if ( Session.user.role == 1 ) { // Marketing
        bannerBlankBorderTextCen ("1. Go to POS System");
        bannerBlankBorderTextCen ("2. Promotion management");
        bannerBlankBorderTextCen ("3. Sales Forecasting");
        bannerBlankBorderTextCen ("4. View Report");
        bannerBlankBorderTextCen ("5. Settings");
        for ( int i = 13; i > 0; i-- )
            bannerBlankBorder ();
    } else { // Sale
        bannerBlankBorderTextCen ("1. Go to POS System");
        bannerBlankBorderTextCen ("2. Settings");
        for ( int i = 16; i > 0; i-- )
            bannerBlankBorder ();
    }
    errorResponse == 1 ? bannerBlankBorderTextCen ("Invalid response. Please try again.") : bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("  Type 'Q' to quit  |      ALTERNATE RESPONSE      |  Type 'B' to logoff");
    bannerFullBorder ();
    bannerUserInput ();
    char flags;
    scanf (" %1c", &flags);
    errorResponse = 0;
    screenClear ();
    if ( Session.user.role == 0 ) { // Manager
        switch ( toupper (flags)) {
            case ('1'):
                cashierInterface (0);
                break;
            case ('2'):
                inventorySwitchHub ();
                break;
            case ('3'):
                customerSwitchHub ();
                break;
            case ('4'):
                personnelSwitchHub ();
                break;
            case ('5'):
                promotionSwitchHub ();
                break;
            case ('6'):
                forecastSwitchHub ();
                break;
            case ('7'):
                reportSwitchHub ();
                break;
            case ('8'):
                settingsSwitchHub ();
                break;
            case ('Q'):
                terminate ();
                break;
            case ('B'):
                deauthenticate ();
                break;
            default:
                errorResponse = 1;
                switchHub ();
        }
    } else if ( Session.user.role == 1 ) { // Marketing
        switch ( toupper (flags)) {
            case ('1'):
                cashierInterface (0);
                break;
            case ('2'):
                promotionSwitchHub ();
                break;
            case ('3'):
                forecastSwitchHub ();
                break;
            case ('4'):
                reportSwitchHub ();
                break;
            case ('5'):
                settingsSwitchHub ();
                break;
            case ('Q'):
                terminate ();
                break;
            case ('B'):
                deauthenticate ();
                break;
            default:
                errorResponse = 1;
                switchHub ();
        }
    } else { // Sale
        switch ( toupper (flags)) {
            case ('1'):
                cashierInterface (0);
                break;
            case ('2'):
                settingsSwitchHub ();
                break;
            case ('Q'):
                terminate ();
                break;
            case ('B'):
                deauthenticate ();
                break;
            default:
                errorResponse = 1;
                switchHub ();
        }
    }
}
