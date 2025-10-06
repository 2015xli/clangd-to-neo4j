// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"

void settingsSwitchHub () {
    screenClear ();

    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Settings Hub");
    bannerBlankBorder ();
    bannerFullBorder ();
    for ( int i = 0; i < 2; i++ )
        bannerBlankBorder ();

    bannerBlankBorderTextCen ("What do you want to do?");

    for ( int i = 0; i < 2; i++ )
        bannerBlankBorder ();
    if ( Session.user.role == 0 ) {
        // Manager
        bannerBlankBorderTextCen ("Authentication");
        bannerBlankBorderTextCen ("--------------");
        bannerBlankBorderTextCen ("1. Change Password");
        bannerBlankBorder ();
        bannerBlankBorder ();
        bannerBlankBorderTextCen ("Storefront");
        bannerBlankBorderTextCen ("----------");
        bannerBlankBorderTextCen ("2. Change store name");
        bannerBlankBorderTextCen ("3. Change store address");
        bannerBlankBorder ();
        bannerBlankBorder ();
        bannerBlankBorderTextCen ("Customer Loyalty Promotion");
        bannerBlankBorderTextCen ("--------------------------");
        bannerBlankBorderTextCen ("4. Edit Point per Price conversion rate");
        bannerBlankBorderTextCen ("5. Edit Price per Point conversion rate");
        bannerBlankBorder ();
        bannerBlankBorder ();
        bannerBlankBorderTextCen ("Others");
        bannerBlankBorderTextCen ("------");
        bannerBlankBorderTextCen ("6. List of contributors");
        bannerBlankBorderTextCen ("7. cat.gif");
        for ( int i = 0; i < 3; i++ )
            bannerBlankBorder ();
    } else if ( Session.user.role == 1 ) { // Marketing
        bannerBlankBorderTextCen ("Authentication");
        bannerBlankBorderTextCen ("--------------");
        bannerBlankBorderTextCen ("1. Change Password");
        bannerBlankBorder ();
        bannerBlankBorder ();
        bannerBlankBorderTextCen ("Customer Loyalty Promotion");
        bannerBlankBorderTextCen ("--------------------------");
        bannerBlankBorderTextCen ("2. Edit Point per Price conversion rate");
        bannerBlankBorderTextCen ("3. Edit Price per Point conversion rate");
        bannerBlankBorder ();
        bannerBlankBorder ();
        bannerBlankBorderTextCen ("Others");
        bannerBlankBorderTextCen ("------");
        bannerBlankBorderTextCen ("4. List of contributors");
        bannerBlankBorderTextCen ("5. cat.gif");
        for ( int i = 0; i < 9; i++ )
            bannerBlankBorder ();
    } else { // Sale
        bannerBlankBorderTextCen ("Authentication");
        bannerBlankBorderTextCen ("--------------");
        bannerBlankBorderTextCen ("1. Change Password");
        bannerBlankBorder ();
        bannerBlankBorder ();
        bannerBlankBorderTextCen ("Others");
        bannerBlankBorderTextCen ("------");
        bannerBlankBorderTextCen ("2. List of contributors");
        bannerBlankBorderTextCen ("3. cat.gif");
        for ( int i = 0; i < 15; i++ )
            bannerBlankBorder ();
    }
    if ( errorResponse == 1 )
        bannerBlankBorderTextCen ("Invalid response. Please try again.");
    else
        bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char flag;
    scanf (" %c", &flag);
    errorResponse = 0;
    if ( Session.user.role == 0 ) {
        // Manager
        switch ( toupper (flag)) {
            case ('1'):
                settingUpdatePasswordInterface ();
                return;
            case ('2'):
                settingUpdateStoreNameInterface ();
                return;
            case ('3'):
                settingUpdateStoreAddressInterface ();
                return;
            case ('4'):
                settingPointToPriceInterface ();
                return;
            case ('5'):
                settingPriceToPointInterface ();
                return;
            case ('6'):
                settingContributorList ();
                settingsSwitchHub ();
                return;
            case ('7'):
                settingCat ();
                return;
            case ('B'):
                switchHub ();
                break;
            case ('Q'):
                terminate ();
                break;
            default:
                errorResponse = 1;
                settingsSwitchHub ();
                break;
        }
    } else if ( Session.user.role == 1 ) {
        // Marketing
        switch ( toupper (flag)) {
            case ('1'):
                settingUpdatePasswordInterface ();
                return;
            case ('2'):
                settingPointToPriceInterface ();
                return;
            case ('3'):
                settingPriceToPointInterface ();
                return;
            case ('4'):
                settingContributorList ();
                return;
            case ('5'):
                settingCat ();
                return;
            case ('B'):
                switchHub ();
                break;
            case ('Q'):
                terminate ();
                break;
            default:
                errorResponse = 1;
                settingsSwitchHub ();
                break;
        }
    } else {
        // Sale
        switch ( toupper (flag)) {
            case ('1'):
                settingUpdatePasswordInterface ();
                return;
            case ('2'):
                settingContributorList ();
                return;
            case ('3'):
                settingCat ();
                return;
            case ('B'):
                switchHub ();
                break;
            case ('Q'):
                terminate ();
                break;
            default:
                errorResponse = 1;
                settingsSwitchHub ();
                break;
        }
    }
}

void settingUpdatePasswordInterface () {
    char oldPassword[MAX_LNG_TEXT], newPasswordBar1[MAX_LNG_TEXT], newPasswordBar2[MAX_LNG_TEXT], flag;
    char firstname[MAX_LNG_TEXT], lastname[MAX_LNG_TEXT], username[MAX_LNG_TEXT], password[MAX_LNG_TEXT], barcodeToken[MAX_LNG_TOKEN];
    int role;
    personnelSelectById (Session.user.id, firstname, lastname, &role, username, password, barcodeToken);
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Settings");
    bannerFullBorder ();
    for ( int i = 0; i < 10; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please type your old Password");
    bannerBlankBorder ();
    for ( int i = 0; i < 21; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    scanf ("%s", oldPassword);
    while ( 1 ) {
        if ( strcmp (oldPassword, password) == 0 ) {
            //Enter First password
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Settings");
            bannerFullBorder ();
            for ( int i = 0; i < 10; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("");
            bannerBlankBorder ();
            for ( int i = 0; i < 21; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please type your new password...");
            bannerFullBorder ();
            bannerUserInput ();
            scanf ("%s", newPasswordBar1);
            //Enter Second password
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Settings");
            bannerFullBorder ();
            for ( int i = 0; i < 10; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("");
            bannerBlankBorder ();
            for ( int i = 0; i < 21; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please retype your new password again...");
            bannerFullBorder ();
            bannerUserInput ();
            scanf ("%s", newPasswordBar2);
            if ( strcmp (newPasswordBar1, newPasswordBar2) == 0 ) {
                personnelUpdatePassword (Session.user.id, newPasswordBar1);
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Settings");
                bannerFullBorder ();
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Your password has been successfully changed!");
                bannerBlankBorder ();
                for ( int i = 0; i < 21; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to quit   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
                scanf (" %c", &flag);
                if ( flag == 'b' || flag == 'B' )
                    settingsSwitchHub ();
                else
                    terminate ();
            } else {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Settings");
                bannerFullBorder ();
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("New password confirmation failed");
                bannerBlankBorder ();
                bannerBlankBorderTextCen ("- Operation Aborted -");
                bannerBlankBorder ();
                for ( int i = 0; i < 19; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to quit   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
                scanf (" %c", &flag);
                if ( flag == 'b' || flag == 'B' )
                    settingsSwitchHub ();
                else
                    terminate ();
            }
        } else {
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Settings");
            bannerFullBorder ();
            for ( int i = 0; i < 10; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Your password is incorrect");
            bannerBlankBorder ();
            for ( int i = 0; i < 21; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please type your old password again... | Type 'B' to back");
            bannerFullBorder ();
            bannerUserInput ();
            scanf ("%s", oldPassword);
            if ( tolower (oldPassword[0]) == 'b' && strlen (oldPassword) == 1 )
                settingsSwitchHub ();
        }
    }
}

void settingUpdateStoreNameInterface () {
    char newstoreName[MAX_LNG_TEXT], flag;
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Settings");
    bannerFullBorder ();
    for ( int i = 0; i < 10; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Your current store's name");
    bannerBlankBorder ();
    bannerBlankBorderTextCen (Setting.storeName);
    bannerBlankBorder ();
    for ( int i = 0; i < 19; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please enter new store name | Type 'B' to Back");
    bannerFullBorder ();
    bannerUserInput ();
    scanf (" %[^\n]", newstoreName);
    if ( tolower (newstoreName[0]) == 'b' && strlen (newstoreName) == 1 ) {
        settingsSwitchHub ();
    } else {
        settingUpdateStoreName (newstoreName);
        screenClear ();
        bannerFullBorder ();
        bannerBlankBorderTextCen ("Settings");
        bannerFullBorder ();
        for ( int i = 0; i < 10; i++ )
            bannerBlankBorder ();
        bannerBlankBorderTextCen ("Your new store name is now");
        bannerBlankBorder ();
        bannerBlankBorderTextCen (newstoreName);
        bannerBlankBorder ();
        for ( int i = 0; i < 19; i++ )
            bannerBlankBorder ();
        bannerBlankBorderTextCen ("Type 'Q' to quit   |      ALTERNATE RESPONSE      |   Type 'B' to back");
        bannerFullBorder ();
        bannerUserInput ();
        scanf (" %c", &flag);
        if ( tolower (flag) == 'b' )
            settingsSwitchHub ();
        else
            terminate ();
    }
}

void settingUpdateStoreAddressInterface () {
    char newstoreAddress[MAX_LNG_TEXT], flag;
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Settings");
    bannerFullBorder ();
    for ( int i = 0; i < 10; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Your current Store Address");
    bannerBlankBorder ();
    bannerBlankBorderTextCen (Setting.storeAddress);
    bannerBlankBorder ();
    for ( int i = 0; i < 19; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please enter new store address | Type 'B' to Back");
    bannerFullBorder ();
    bannerUserInput ();
    scanf (" %[^\n]", newstoreAddress);
    if ( tolower (newstoreAddress[0]) == 'b' && strlen (newstoreAddress) == 1 ) {
        settingsSwitchHub ();
    } else {
        settingUpdateAddress (newstoreAddress);
        screenClear ();
        bannerFullBorder ();
        bannerBlankBorderTextCen ("Settings");
        bannerFullBorder ();
        for ( int i = 0; i < 10; i++ )
            bannerBlankBorder ();
        bannerBlankBorderTextCen ("Your store adress has been changed to");
        bannerBlankBorder ();
        bannerBlankBorderTextCen (newstoreAddress);
        bannerBlankBorder ();
        for ( int i = 0; i < 19; i++ )
            bannerBlankBorder ();
        bannerBlankBorderTextCen ("Type 'Q' to quit   |      ALTERNATE RESPONSE      |   Type 'B' to back");
        bannerFullBorder ();
        bannerUserInput ();
        scanf (" %c", &flag);
        if ( tolower (flag) == 'b' )
            settingsSwitchHub ();
        else
            terminate ();
    }
}

void settingContributorList () {
    char text[200];
    for (int i = 10;i>0;i--) {
        screenClear ();
        bannerCenBorder ("Educational purpose only", "Redistribution of project is not allowed",
                         "Created by the 1st year student IT KMITL 14", "POS Version 1.0");
        bannerBlankBorder ();
        bannerBlankBorder ();
        bannerBlankBorderTextCen ("Lists of team members");
        bannerFullBorderSection ();
        bannerBlankBorderTextCen ("Kunanon   Srisuntiroj   @sagelga      59070022");
        bannerBlankBorderTextCen ("Thanawat  Laodkaew      @skydddoogg   59070071");
        bannerBlankBorderTextCen ("Noppanut  Ploywong      @noppanut15   59070082");
        bannerBlankBorderTextCen ("Vasanchai Prakobkij     @59070156     59070156");
        bannerBlankBorderTextCen ("Weerakorn Pongpum       @fablemay     59070163");
        for ( int i = 2; i > 0; i-- )
            bannerBlankBorder ();
        bannerBlankBorderTextCen (
                "Over 8000 lines of pure C language has been neatly crafted with love and passion <3");
        bannerBlankBorderTextCen ("See our GitHub Repository : https://github.com/sagelga/ComPro_Project");
        for ( int i = 18; i > 0; i-- )
            bannerBlankBorder ();
        strcpy(text," ");
        sprintf(text,"Redirecting you back in %d second(s)",i);
        bannerBlankBorderTextCen (text);
        bannerFullBorder ();
        delay (1);
    }
}

void settingCat () {
    int i = 0;
    char text1[300] = "", text2[300] = "", text3[300] = "", text4[300] = "";

    for ( int i = 0; i < 88; i++ ) {
        screenClear ();

        bannerFullBorder ();

        for ( int k = 7; k > 0; k-- ) { // Cat count
            i++;
            strcpy (text1, " ");
            strcpy (text2, " ");
            strcpy (text3, " ");
            strcpy (text4, " ");
            for ( int j = i; j > 0; j-- ) {
                strcat (text1, "_");
            }
            strcat (text1, "━━━━___━*━___━━___━___*___━_*___┓╭━━━━━━━━━━━━╮");
            printf ("%s\n", text1);
            for ( int j = i; j > 0; j-- ) {
                strcat (text2, "_");
            }
            strcat (text2, "___━━__*_━━___━━___━━*____━━___┗┓|::::::^----^|");
            printf ("%s\n", text2);
            for ( int j = i; j > 0; j-- ) {
                strcat (text3, "_");
            }
            strcat (text3, "___━━___━━___━*━___━━____━━*___━┗|:::::|｡◕‿‿◕｡|");
            printf ("%s\n", text3);
            for ( int j = i; j > 0; j-- ) {
                strcat (text4, "_");
            }
            strcat (text4, "___━━___*━__━━_*___━━___*━━___*━━╰O--O---O--O ╯");
            printf ("%s\n", text4);
            printf ("\n");
        }
        bannerBlankBorderTextCen ("~ ~ ~ Nyan Nyan Nyan ~ ~ ~");
        bannerBlankBorderTextCen (
                "The flying cat is crossing the galaxy. You can cross very soon");
        bannerFullBorder ();
        delay (1);
    }
    settingsSwitchHub ();
}

void settingUpdateStoreName (char *storeName) {
    strcpy (Setting.storeName, storeName);
    settingFileWrite ();    // Save to a Database file
}

void settingUpdateAddress (char *storeAddress) {
    strcpy (Setting.storeAddress, storeAddress);
    settingFileWrite ();    // Save to a Database file
}

void settingPriceToPointInterface () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Price to Point Conversion Rate");
    bannerBlankBorder ();
    bannerFullBorder ();
    for ( int i = 2; i > 0; i-- )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Your current conversion rate");
    bannerBlankBorder ();
    char text[140];
    sprintf (text, "1 baht you pay  ->   You earns %.2f point", Setting.priceToPoint);
    bannerBlankBorderTextCen (text);
    bannerBlankBorderTextCen ("________________");
    strcpy (text, " ");
    sprintf (text, "10 baht   ->   %.2f point", Setting.priceToPoint * 10);
    bannerBlankBorderTextCen (text);
    strcpy (text, " ");
    sprintf (text, "20 baht   ->   %.2f point", Setting.priceToPoint * 20);
    bannerBlankBorderTextCen (text);
    strcpy (text, " ");
    sprintf (text, "50 baht   ->   %.2f point", Setting.priceToPoint * 50);
    bannerBlankBorderTextCen (text);
    strcpy (text, " ");
    sprintf (text, "100 baht   ->   %.2f point", Setting.priceToPoint * 100);
    bannerBlankBorderTextCen (text);
    bannerBlankBorder ();
    if ( completeMark == 0 )
        bannerBlankBorder ();
    else
        bannerBlankBorderTextCen ("Change is now saved.");
    for ( int i = 18; i > 0; i-- )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Would you like to change a conversion rate?");
    bannerBlankBorderTextCen ("Type 'Q' to stop   | Type 'Y' to continue  |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char flag;
    scanf (" %c", &flag);
    completeMark = 0;
    switch ( toupper (flag)) {
        case ('Y'):
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextCen ("Price to Point Conversion Rate");
            bannerBlankBorder ();
            bannerFullBorder ();
            for ( int i = 2; i > 0; i-- )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Your current conversion rate");
            bannerBlankBorder ();
            char text[140];
            sprintf (text, "1 baht you pay  ->   You earns %.2f point", Setting.priceToPoint);
            bannerBlankBorderTextCen (text);
            bannerBlankBorderTextCen ("________________");
            strcpy (text, " ");
            sprintf (text, "10 baht   ->   %.2f point", Setting.priceToPoint * 10);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "20 baht   ->   %.2f point", Setting.priceToPoint * 20);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "50 baht   ->   %.2f point", Setting.priceToPoint * 50);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "100 baht   ->   %.2f point", Setting.priceToPoint * 100);
            bannerBlankBorderTextCen (text);
            for ( int i = 21; i > 0; i-- )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("What is your new convertion rate?");
            bannerFullBorder ();
            bannerUserInput ();
            // This will ask for new conversion rate
            double newConversionRate;
            scanf ("%lf", &newConversionRate);
            // New conversion rate displays
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextCen ("Price to Point Conversion Rate");
            bannerBlankBorder ();
            bannerFullBorder ();
            for ( int i = 2; i > 0; i-- )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Your current conversion rate");
            bannerBlankBorder ();
            strcpy (text, " ");
            sprintf (text, "1 baht   ->   %.2f (from %.2f) point", newConversionRate, Setting.priceToPoint);
            bannerBlankBorderTextCen (text);
            bannerBlankBorderTextCen ("________________");
            strcpy (text, " ");
            sprintf (text, "10 baht   ->   %.2f (from %.2f) point", newConversionRate * 10, Setting.priceToPoint * 10);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "20 baht   ->   %.2f (from %.2f) point", newConversionRate * 20, Setting.priceToPoint * 20);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "50 baht   ->   %.2f (from %.2f) point", newConversionRate * 50, Setting.priceToPoint * 50);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "100 baht   ->   %.2f (from %.2f) point", newConversionRate * 100,
                     Setting.priceToPoint * 100);
            bannerBlankBorderTextCen (text);
            for ( int i = 20; i > 0; i-- )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Do you want to save your change?");
            bannerBlankBorderTextCen ("Type 'Q' to stop  |  Type 'Y' to continue  |  Type 'B' to back");
            bannerFullBorder ();
            bannerUserInput ();
            char flag2;
            scanf (" %c", &flag2);
            errorResponse = 0;
            switch ( toupper (flag2)) {
                case ('Y'):
                    settingUpdatePriceToPoint (newConversionRate);
                    completeMark = 1;
                    settingPriceToPointInterface ();
                    return;
                case ('N'):
                    settingPriceToPointInterface ();
                    return;
                case ('B'):
                    settingPriceToPointInterface ();
                    return;
                case ('Q'):
                    terminate ();
                    return;
            }
        case ('B'):
            settingsSwitchHub ();
            return;
        case ('Q'):
            terminate ();
            return;
        default:
            errorResponse = 1;
            settingPriceToPointInterface ();
            return;
    }
}

void settingPointToPriceInterface () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Point to Price Conversion Rate");
    bannerBlankBorder ();
    bannerFullBorder ();
    for ( int i = 2; i > 0; i-- )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Your current conversion rate");
    bannerBlankBorder ();
    char text[140];
    sprintf (text, "You use %.2f point   ->   Get 1 baht discount", Setting.pointToPrice);
    bannerBlankBorderTextCen (text);
    bannerBlankBorderTextCen ("________________");
    strcpy (text, " ");
    sprintf (text, "%.2f point   ->   10 baht", Setting.pointToPrice * 10);
    bannerBlankBorderTextCen (text);
    strcpy (text, " ");
    sprintf (text, "%.2f point   ->   20 baht", Setting.pointToPrice * 20);
    bannerBlankBorderTextCen (text);
    strcpy (text, " ");
    sprintf (text, "%.2f point   ->   50 baht", Setting.pointToPrice * 50);
    bannerBlankBorderTextCen (text);
    strcpy (text, " ");
    sprintf (text, "%.2f point   ->   100 baht", Setting.pointToPrice * 100);
    bannerBlankBorderTextCen (text);
    bannerBlankBorder ();
    if ( completeMark == 0 )
        bannerBlankBorder ();
    else
        bannerBlankBorderTextCen ("Change is now saved.");
    for ( int i = 18; i > 0; i-- )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Would you like to change a conversion rate?");
    bannerBlankBorderTextCen ("Type 'Q' to stop   | Type 'Y' to continue  |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char flag;
    scanf (" %c", &flag);
    completeMark = 0;
    switch ( toupper (flag)) {
        case ('Y'):
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextCen ("Point to Price Conversion Rate");
            bannerBlankBorder ();
            bannerFullBorder ();
            for ( int i = 2; i > 0; i-- )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Your current conversion rate");
            bannerBlankBorder ();
            char text[140];
            sprintf (text, "You use %.2f point   ->   Get 1 baht discount", Setting.pointToPrice);
            bannerBlankBorderTextCen (text);
            bannerBlankBorderTextCen ("________________");
            strcpy (text, " ");
            sprintf (text, "%.2f point   ->   10 baht", Setting.pointToPrice * 10);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "%.2f point   ->   20 baht", Setting.pointToPrice * 20);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "%.2f point   ->   50 baht", Setting.pointToPrice * 50);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "%.2f point   ->   100 baht", Setting.pointToPrice * 100);
            for ( int i = 22; i > 0; i-- )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("What is your new convertion rate?");
            bannerFullBorder ();
            bannerUserInput ();
            // This will ask for new conversion rate
            double newConversionRate;
            scanf ("%lf", &newConversionRate);
            // New conversion rate displays
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextCen ("Point to Price Conversion Rate");
            bannerBlankBorder ();
            bannerFullBorder ();
            for ( int i = 2; i > 0; i-- )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Your current conversion rate");
            bannerBlankBorder ();
            strcpy (text, " ");
            sprintf (text, "You use %.2f (from %.2f) point   ->   Get 1 baht discount", newConversionRate,
                     Setting.pointToPrice);
            bannerBlankBorderTextCen (text);
            bannerBlankBorderTextCen ("________________");
            strcpy (text, " ");
            sprintf (text, "%.2f (from %.2f) point   ->   10 baht", newConversionRate * 10, Setting.pointToPrice * 10);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "%.2f (from %.2f) point   ->   20 baht", newConversionRate * 20, Setting.pointToPrice * 20);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "%.2f (from %.2f) point   ->   50 baht", newConversionRate * 50, Setting.pointToPrice * 50);
            bannerBlankBorderTextCen (text);
            strcpy (text, " ");
            sprintf (text, "%.2f (from %.2f) point   ->   100 baht", newConversionRate * 100,
                     Setting.pointToPrice * 100);
            for ( int i = 21; i > 0; i-- )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Do you want to save your change?");
            bannerBlankBorderTextCen ("Type 'Q' to stop  |  Type 'Y' to continue  |  Type 'B' to back");
            bannerFullBorder ();
            bannerUserInput ();
            char flag2;
            scanf (" %c", &flag2);
            errorResponse = 0;
            switch ( toupper (flag2)) {
                case ('Y'):
                    settingUpdatePointToPrice (newConversionRate);
                    completeMark = 1;
                    settingPointToPriceInterface ();
                    return;
                case ('N'):
                    settingPointToPriceInterface ();
                    return;
                case ('B'):
                    settingPointToPriceInterface ();
                    return;
                case ('Q'):
                    terminate ();
                    return;
            }
        case ('B'):
            settingsSwitchHub ();
            return;
        case ('Q'):
            terminate ();
            return;
        default:
            errorResponse = 1;
            settingPointToPriceInterface ();
            return;
    }
}

void settingUpdatePriceToPoint (double priceToPoint) {
    Setting.priceToPoint = priceToPoint;
    settingFileWrite ();    // Save to a Database file
}

void settingUpdatePointToPrice (double pointToPrice) {
    Setting.pointToPrice = pointToPrice;
    settingFileWrite ();    // Save to a Database file
}
