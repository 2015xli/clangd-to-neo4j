// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"

void promotionSwitchHub () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Promotion Management");
    bannerBlankBorder ();
    bannerFullBorder ();
    for ( int i = 0; i < 10; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("What do you want to do ?");
    bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("1. Preview promotion in database");
    bannerBlankBorderTextCen ("2. Create a new promotion");
    bannerBlankBorderTextCen ("3. Delete promotion from database");
    bannerBlankBorderTextCen ("4. Update promotion metadata");
    for ( int i = 0; i < 12; i++ )
        bannerBlankBorder ();
    if ( errorResponse == 1 )
        bannerBlankBorderTextCen ("Invalid response. Please try again.");
    else
        bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit  |      ALTERNATE RESPONSE      |  Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char flag;
    scanf (" %c", &flag);
    switch (toupper (flag)) {
        case ('1'):
            promotionSelectInterface ();
            break;
        case ('2'):
            promotionInsertInterface ();
            break;
        case ('3'):
            promotionDeleteInterface ();
            break;
        case ('4'):
            promotionUpdateInterface ();
            break;
        case ('B'):
            switchHub ();
        case ('Q'):
            terminate ();
        default:
            promotionSwitchHub ();
            return;
    }
}

void promotionInsertInterface () {
    char bufferHead[140];
    sprintf (bufferHead, "%-100s|%-20s|%s", "ID", "Price", "Status");
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Promotion Database");
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Insert Promotion");
    bannerFullBorderSection ();
    bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Insert in form");
    bannerBlankBorderTextCen ("Form: ID");
    bannerBlankBorderTextCen ("Price");
    bannerBlankBorderTextCen (" ");
    bannerBlankBorderTextCen ("Ex: 1234567891012");
    bannerBlankBorderTextCen ("100");
    for ( int i = 0; i < 23; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char id[MAX_LNG_ID], buffer[140], flag;
    double price;
    while ( 1 ) {
        scanf ("%s", id);
        if ( strcmp (id, "B") == 0 || strcmp (id, "b") == 0 ) {
            promotionSwitchHub ();
            break;
        } else if ( strcmp (id, "Q") == 0 || strcmp (id, "q") == 0 ) {
            terminate ();
            break;
        } else {
            //------------------After Input ID--------------------
            sprintf (buffer, "%-100s", id);
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Promotion Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 28; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
            bannerFullBorder ();
            bannerUserInput ();
            //---------------------Price--------------------------
            scanf ("%lf", &price);
            sprintf (buffer, "%-100s %-20.2lf %s", id, price, "Active");
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Promotion Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 10; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Are you sure to insert this promotion ?");
            bannerBlankBorder ();
            bannerBlankBorderTextCen ("Type 'Y' to comfirm || Type 'N' to Discard");
            for ( int i = 0; i < 15; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
            bannerFullBorder ();
            bannerUserInput ();
            scanf (" %c", &flag);
            if ( flag == 'Y' || flag == 'y' ) {
                if ( promotionInsert (id, price)) {
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Promotion Database");
                    bannerFullBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (bufferHead);
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft ("->");
                    for ( int i = 0; i < 10; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Insert Success");
                    bannerBlankBorderTextCen ("Insert Next PromotionID or Type 'B' to Back");
                    for ( int i = 0; i < 16; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                } else {
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Promotion Database");
                    bannerFullBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (bufferHead);
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (buffer);
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft ("->");
                    for ( int i = 0; i < 10; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Can't Insert Promotion");
                    bannerBlankBorderTextCen ("_____________________");
                    bannerBlankBorder ();
                    bannerBlankBorderTextCen ("This PromotionID was duplicated");
                    bannerBlankBorderTextCen ("Insert Next PromotionID or Type 'B' to Back");

                    for ( int i = 0; i < 11; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                }
            } else {
                screenClear ();
                promotionInsertInterface ();
            }
        }
    }
}

void displayPromotion (int page) {
    screenClear ();
    int allPage = (int) ceil (RecordCount.promotion / 32) + 1;
    char NewState[7];
    bannerFullBorder ();
    printf ("::                         %-42s |              %-18s |              %-18s ::\n", "Promotion ID", "Price",
            "Status");
    bannerFullBorder ();
    if ( page == allPage ) {
        for ( int i = (page - 1) * 32; i < RecordCount.promotion; ++i ) {
            if ( Promotion[i].status ) {
                strcpy (NewState, "Active");
            } else {
                strcpy (NewState, "Used");
            }
            printf ("::                        %-43s | %31.2lf |              %-18s ::\n", Promotion[i].id,
                    Promotion[i].price,
                    NewState);
        }
        //display remaining line as bannerBlankBorder()
        for ( int i = 0; i < 32 - (RecordCount.promotion % 32); ++i )
            printf (":: %-66s | %31s | %-31s ::\n", "", "", "");
    } else {
        for ( int i = (page - 1) * 32; i < page * 32/*(34*page)*/; ++i ) {
            if ( Promotion[i].status )
                strcpy (NewState, "Active");
            else
                strcpy (NewState, "Used");
            printf ("::                       %-43s | %31.2lf |              %-18s ::\n", Promotion[i].id,
                    Promotion[i].price,
                    NewState);
        }
    }
    bannerBlankBorderTextCen ("Enter Page/Enter 'B' to back to Promotion Menu");
    printf ("::                                                       <<  <  ( Page %d of %d ) > >>                                                      ::\n",
            page, allPage);
    bannerFullBorder ();
    bannerUserInput ();
}

void promotionSelectInterface () {
    char handling;
    int pageIn = 1, CheckPage;
    displayPromotion (1);
    for ( int i = 0; i >= 0; ++i ) {
        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            screenClear ();
            promotionSwitchHub ();
        } else if ( isdigit (handling)) {
            CheckPage = (int) handling - 48;
            if ((CheckPage <= ((int) ceil (RecordCount.promotion / 32) + 1)) && (CheckPage >= 1)) {
                pageIn = (int) handling - 48;
                displayPromotion (pageIn);
            } else {
                displayPromotion (pageIn);
                printf ("Oops! Page not found, Please enter correct page: ");
            }
        } else {
            displayPromotion (pageIn);
            printf ("Oops! Input Error, Please enter correctly: ");
        }
    }
}

void promotionDeleteInterface () {
    char bufferHead[140];
    sprintf (bufferHead, "%-100s|%-20s|%s", "ID", "Price", "Status");
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Promotion Database");
    bannerFullBorder ();
    bannerBlankBorder ();

    bannerBlankBorderTextLeft (bufferHead);

    bannerFullBorderSection ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft ("->");
    for ( int i = 0; i < 10; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please type PromotionID");
    for ( int i = 0; i < 17; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char id[MAX_LNG_ID], buffer[140], flag, statusShow[MAX_LNG_ID];
    double price;
    int status;
    while ( 1 ) {
        scanf ("%s", id);
        if ( strcmp (id, "B") == 0 || strcmp (id, "b") == 0 ) {
            promotionSwitchHub ();
        } else if ( strcmp (id, "Q") == 0 || strcmp (id, "q") == 0 ) {
            terminate ();
        } else {
            if ( promotionSelectById (id, &price, &status)) {
                screenClear ();
                if ( status == 1 )
                    strcpy (statusShow, "Active");
                else
                    strcpy (statusShow, "Used");
                sprintf (buffer, "%-100s %-20.2lf %s", id, price, statusShow);
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Promotion Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (buffer);
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Are you sure to delete ?");
                bannerBlankBorderTextCen ("Type 'Y' to comfirm || Type 'N' to Discard");
                for ( int i = 0; i < 16; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
                scanf (" %c", &flag);
                if ( flag == 'Y' || flag == 'y' ) {
                    promotionDelete (id);
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Promotion Database");
                    bannerFullBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (bufferHead);
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft ("->");
                    for ( int i = 0; i < 10; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Delete Success");
                    bannerBlankBorderTextCen ("Type Next PromotionID Or Type 'B' to Back");
                    for ( int i = 0; i < 16; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                } else {
                    screenClear ();
                    promotionDeleteInterface ();
                }
            } else {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Promotion Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft ("->");
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("PromotionID dosen't exist.");
                bannerBlankBorderTextCen ("Type Next PromotionID Or Type 'B' to Back");
                for ( int i = 0; i < 16; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
            }
        }
    }
}

void promotionUpdateInterface () {
    char bufferHead[140];
    sprintf (bufferHead, "%-100s|%-20s|%s", "ID", "Price", "Status");
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Promotion Database");
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft (bufferHead);
    bannerFullBorderSection ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft ("->");
    for ( int i = 0; i < 10; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type PromotionID");
    for ( int i = 0; i < 17; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char id[MAX_LNG_ID], buffer[140], flag[100], statusShow[MAX_LNG_ID];
    double price;
    int status;
    while ( 1 ) {
        scanf ("%s", id);
        if ( strcmp (id, "B") == 0 || strcmp (id, "b") == 0 ) {
            promotionSwitchHub ();
        } else if ( strcmp (id, "Q") == 0 || strcmp (id, "q") == 0 ) {
            terminate ();
        } else {
            if ( promotionSelectById (id, &price, &status)) {
                screenClear ();
                if ( status == 1 )
                    strcpy (statusShow, "Active");
                else
                    strcpy (statusShow, "Used");
                sprintf (buffer, "%-100s ->%-20.2lf %s", id, price, statusShow);
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Promotion Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (buffer);
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                for ( int i = 0; i < 21; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type new price || Press Enter to set by default");
                bannerFullBorder ();
                printf ("Default Price: (%lf) >>> ", price);
                if ( superscanf (flag) != 0 )
                    promotionUpdatePrice (id, atof (flag));
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Promotion Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                promotionSelectById (id, &price, &status);
                sprintf (buffer, "%-100s %-20.2lf %s", id, price, statusShow);
                bannerBlankBorderTextLeft (buffer);
                bannerBlankBorderTextLeft ("->");
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Promotion has been updated");
                bannerBlankBorderTextCen ("Type Next PromotionID to Update Or Type 'B' to Back");
                for ( int i = 0; i < 15; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
            } else {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Promotion Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft ("->");
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("PromotionID dosen't exist.");
                bannerBlankBorderTextCen ("Type Next PromotionID Or Type 'B' to Back");
                for ( int i = 0; i < 16; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
            }

        }
    }
}

int promotionSelectById (char *id, double *price, int *status) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.promotion;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Promotion[i].id, id) == 0 ) {
            // Return all values back by reference
            *price = Promotion[i].price;
            *status = Promotion[i].status;
            return 1;   // Found a record
        }
    }
    return 0;           // Not found the given `id` in the records
}

int promotionInsert (char *id, double price) {
    int tailIndex = RecordCount.promotion;
    // To comfirm that `id` is unique
    for ( int i = 0; i < tailIndex; i++ ) {
        if ( strcmp (Promotion[i].id, id) == 0 )
            return 0;   // Error: Barcode ID already exists
    }
    strcpy (Promotion[tailIndex].id, id);
    Promotion[tailIndex].price = price;
    Promotion[tailIndex].status = 1;        // Initail Value (1 = Active)
    RecordCount.promotion++;                // Update the amount of records
    promotionFileWrite ();                   // Save to a Database file
    return 1;                   // Operation Success
}

int promotionUpdatePrice (char *id, double price) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.promotion;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Promotion[i].id, id) == 0 ) {
            Promotion[i].price = price;
            promotionFileWrite ();    // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int promotionUpdateStatus (char *id, int status) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.promotion;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Promotion[i].id, id) == 0 ) {
            Promotion[i].status = status;
            promotionFileWrite ();    // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int promotionDelete (char *id) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.promotion;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Promotion[i].id, id) == 0 ) {
            while ( i < numberOfRecords - 1 ) {
                Promotion[i] = Promotion[i + 1];
                i++;
            }
            RecordCount.promotion--;    // Update the amount of records
            promotionFileWrite ();       // Save to a Database file
            return 1;                  // Record successfully deleted
        }
    }
    return 0;   // Not found the given `id` in the records
}
