#include "main.h"

void authInterface () {
    screenClear ();

    bannerCenBorder ("", "", "", "POS Version : 1.0");

    for ( int i = 3; i > 0; i-- )
        bannerBlankBorder ();

    bannerBlankBorderTextCen ("Please type in your username");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("(or scan the Personnel token code)");
    for ( int i = 0; i < 25; i++ )
        bannerBlankBorder ();
    bannerFullBorder ();

    char username[MAX_LNG_TOKEN]; // Copy data to SESSION struct;
    bannerUserInput ();
    scanf (" %[^\n]", username); // Then save to session struct

    // First Check the Token ID
    if ( authenticateByToken (username)) {
        authInterfaceComplete ();
    }
    // If token is invalid then ask the password (Identify as Normal Login)
    screenClear ();

    bannerCenBorder ("", "", "", "POS Version : 1.0");

    for ( int i = 3; i > 0; i-- )
        bannerBlankBorder ();

    char text[137];
    sprintf (text, "Welcome back %s!", username);
    bannerBlankBorderTextCen (text);
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("And your password is?");

    for ( int i = 0; i < 24; i++ )
        bannerBlankBorder ();

    bannerBlankBorderTextCen ("Please type in your password");
    bannerFullBorder ();
    bannerUserInput ();

    char password[130];
    scanf ("%s", password);

    if ( authenticateByUsername (username, password) == 1 ) { // If the username and the password is matched from the database
        authInterfaceComplete ();
    } else if ( authenticateByUsername (username, password) == 0 ) { // If the username and the password is not matched from the database
        authInterfaceFail ();
    } else {// If username does not exist
        authInterfaceError ();
    }
}

void authInterfaceComplete () {
    screenClear ();

    bannerCenBorder ("", "", "", "POS Version : 1.0");

    for ( int i = 3; i > 0; i-- )
        bannerBlankBorder ();

    char text[140];
    sprintf (text, "Welcome back %s %s!", Session.user.firstname, Session.user.lastname);
    bannerBlankBorderTextCen (text);
    bannerBlankBorder ();

    char text2[140];
    sprintf (text2, "Signing in as : %s", Session.user.username);
    bannerBlankBorderTextCen (text2);

    for ( int i = 2; i > 0; i-- )
        bannerBlankBorder ();

    printf ("::                                                                 ██████                                                                 ::\n");
    printf ("::                                                                ██    ██                                                                ::\n");
    printf ("::                                                               ██      ██                                                               ::\n");
    printf ("::                                                               ██████████                                                               ::\n");
    printf ("::                                                               ████  ████                                                               ::\n");
    printf ("::                                                               ████  ████                                                               ::\n");
    printf ("::                                                               ██████████                                                               ::\n");

    for ( int i = 2; i > 0; i-- )
        bannerBlankBorder ();

    bannerBlankBorderTextCen ("POS system is LOCKED");

    for ( int i = 0; i < 13; i++ ) {
        bannerBlankBorder ();
    }
    bannerFullBorder ();

    delay (2);

    screenClear ();

    bannerCenBorder ("", "", "", "POS Version : 1.0");

    for ( int i = 3; i > 0; i-- )
        bannerBlankBorder ();

    bannerBlankBorderTextCen (text);
    bannerBlankBorder ();

    bannerBlankBorderTextCen (text2);

    for ( int i = 2; i > 0; i-- )
        bannerBlankBorder ();

    printf ("::                                                                 ██████                                                                 ::\n");
    printf ("::                                                                ██    ██                                                                ::\n");
    printf ("::                                                                       ██                                                               ::\n");
    printf ("::                                                               ██████████                                                               ::\n");
    printf ("::                                                               ████  ████                                                               ::\n");
    printf ("::                                                               ████  ████                                                               ::\n");
    printf ("::                                                               ██████████                                                               ::\n");

    for ( int i = 2; i > 0; i-- )
        bannerBlankBorder ();

    bannerBlankBorderTextCen ("POS system is now UNLOCK");


    for ( int i = 0; i < 12; i++ ) {
        bannerBlankBorder ();
    }

    bannerBlankBorderTextCen ("Redirecting you to POS system...");
    bannerFullBorder ();
    delay (3);

    switchHub ();
}

void authInterfaceFail () {
    screenClear ();

    bannerCenBorder ("", "", "", "POS Version : 1.0");

    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Your login credentials is incorrect.");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("We are redirecting you try again. If you wish to do that, type any key to continue");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("or type 'Q' to exit the program");

    for ( int i = 0; i < 25; i++ )
        bannerBlankBorder ();

    bannerFullBorder ();
    bannerUserInput ();
    char flag;
    scanf (" %1c", &flag);

    switch ( toupper (flag)) {

        case ('Q'):
            terminate ();
            return;

        default:
            screenClear ();
            authInterface ();
            return;
    }
    // If user type anything (except N or n) program will not be terminate + rerouting to login page again
    // If user type 'N' or 'n' program will be rerouting to terminate(); and they can shut the program down...
}

void authInterfaceError () {
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Oops!");
    bannerFullBorder ();

    bannerBlankBorderTextCen ("Username does not exist in our database.");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please try again or contact an administrator if this occur too many times");
    for ( int i = 0; i < 31; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Redirect to sign in...");
    bannerFullBorder ();

    delay (4);
    authInterface ();
}

int authenticateByUsername (char *username, char *password) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.personnel;

    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Personnel[i].username, username) == 0 ) {
            if ( strcmp (Personnel[i].password, password) == 0 ) {
                // Save user's information on the Session
                Session.user = Personnel[i];
                Session.isLogedin = 1;
                return 1;   // Login success
            } else
                return 0;   // Password incorrect
        }
    }
    return -1;  // User Not found
}

int authenticateByToken (char *barcodeToken) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.personnel;

    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Personnel[i].barcodeToken, barcodeToken) == 0 ) {
            // Save user's information on the Session
            Session.user = Personnel[i];
            Session.isLogedin = 1;
            return 1;
        }
    }
    return 0;
}

void deauthenticate () {
    Session.isLogedin = 0;

    screenClear ();
    bannerFullBorder ();

    for ( int i = 17; i > 0; i-- )
        bannerBlankBorder ();

    char text[137];
    sprintf(text,"User %s has successfully log out.",Session.user.username);
    bannerBlankBorderTextCen (text);

    for ( int i = 17; i > 0; i-- )
        bannerBlankBorder ();

    bannerBlankBorderTextCen ("Returning you back to login...");
    bannerFullBorder ();

    delay (3);
    authInterface ();
}
