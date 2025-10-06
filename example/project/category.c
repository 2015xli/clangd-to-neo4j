// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"

int categorySelectById (unsigned int id, char *name) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.category;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( Category[i].id == id ) {
            // Return all values back by reference
            strcpy (name, Category[i].name);

            return 1;   // Found a record
        }
    }
    return 0;           // Not found the given `id` in the records
}

int categoryInsert (char *name) {
    int tailIndex = RecordCount.category;
    // To confirm that `name` is unique
    for ( int i = 0; i < tailIndex; i++ ) {
        if ( strcmp (Category[i].name, name) == 0 )
            return 0;   // Error: Category name already exists
    }
    Category[tailIndex].id = tailIndex; // Auto-increment
    strcpy (Category[tailIndex].name, name);
    RecordCount.category++;    // Update the amount of records
    categoryFileWrite ();       // Save to a Database file
    return 1;                  // Operation Success
}

int categoryUpdateName (unsigned int id, char *name) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.category;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( Category[i].id == id ) {
            strcpy (Category[i].name, name);
            categoryFileWrite ();    // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

void displayCategory (int page) {
    screenClear ();
    int allPage = (int) ceil (RecordCount.category / 32) + 1;
    bannerFullBorder ();
    printf ("::          ID           | Category Name                                                                                                  ::\n");
    bannerFullBorder ();
    if ( page == allPage ) {
        for ( int i = (page - 1) * 32; i < RecordCount.category; ++i )
            printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
        for ( int i = 0; i < 32 - (RecordCount.category % 32); ++i )
            printf ("::                       |                                                                                                                ::\n");
    } else {
        for ( int i = (page - 1) * 32; i < page * 32/*(32*page)*/; ++i )
            printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
    }
    bannerBlankBorderTextCen ("Enter Page Number | Type 'B' to back");
    printf ("::                                                       <<  <  ( Page %d of %d ) > >>                                                      ::\n",
            page, allPage);
    bannerFullBorder ();
    bannerUserInput ();
}
void categoryDatabaseInterface () {
    char handling;
    int pageIn = 1, CheckPage;
    displayCategory (1);
    for ( int i = 0; i >= 0; ++i ) {
        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            screenClear ();
            inventorySwitchHub ();
        } else if ( isdigit (handling)) {
            CheckPage = (int) handling - 48;
            if ((CheckPage <= ((int) ceil (RecordCount.inventory / 32) + 1)) && (CheckPage >= 1)) {
                pageIn = (int) handling - 48;
                displayCategory (pageIn);
            } else {
                displayCategory (pageIn);
                printf ("Oops! Page not found, Please enter correct page: ");
            }
        } else {
            displayCategory (pageIn);
            printf ("Oops! Input Error, Please enter correctly: ");
        }
    }
}
void categoryAdd () {
    screenClear ();
    char nameIN[MAX_LNG_TEXT];
    char handling;
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Insert Category");
    bannerFullBorder ();
    printf ("::          ID           | Category Name                                                                                                  ::\n");
    bannerFullBorder ();
    for ( int i = 0; i < RecordCount.category; ++i )
        printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
    for ( int i = 0; i < (33 - RecordCount.category - 2); ++i )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    for ( int i = 0; i >= 0; ++i ) {
        printf ("\n");
        printf ("Enter the Category name to add >>> ");
        scanf (" %[^\n]", nameIN);
        if ((strcmp (nameIN, "B") == 0) || (strcmp (nameIN, "b") == 0)) {
            inventorySwitchHub ();
        } else if ((strcmp (nameIN, "Q") == 0) || (strcmp (nameIN, "q") == 0)) {
            terminate ();
        } else {
            if ( categoryInsert (nameIN)) {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Insert Category");
                bannerFullBorder ();
                printf ("::          ID           | Category Name                                                                                                  ::\n");
                bannerFullBorder ();
                for ( int i = 0; i < RecordCount.category; ++i )
                    printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
                for ( int i = 0; i < (32 - RecordCount.category - 3); ++i )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Successful!!! The category has been inserted.");
                bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
            } else {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Insert Category");
                bannerFullBorder ();
                printf ("::          ID           | Category Name                                                                                                  ::\n");
                bannerFullBorder ();
                for ( int i = 0; i < RecordCount.category; ++i )
                    printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
                for ( int i = 0; i < 32 - RecordCount.category - 3; ++i )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Error!!! Category name already exists");
                bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
            }
        }
    }
}
void categoryEdit () {
    char bufferHead[140];
    sprintf (bufferHead, "%-60s|%s", "ID", "CategoryName");
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Category Database");
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft (bufferHead);
    bannerFullBorderSection ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft ("->");
    bannerBlankBorder ();
    bannerFullBorder ();
    printf ("::          ID           | Category Name                                                                                                  ::\n");
    bannerFullBorder ();
    for ( int i = 0; i < RecordCount.category; ++i )
        printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
    for ( int i = 0; i < (27 - (RecordCount.category - 1 - 4)); i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please type the Category ID");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char id[MAX_LNG_TEXT], name[MAX_LNG_TEXT], buffer[MAX_LNG_SCREEN], flag[MAX_LNG_TEXT];
    while ( 1 ) {
        scanf ("%s", id);
        if ( tolower (id[0]) == 'b' ) {
            inventorySwitchHub ();
        } else if ( tolower (id[0]) == 'q' ) {
            terminate ();
        } else {
            if ( categorySelectById (strtoul (id, NULL, 10), name)) {
                screenClear ();
                sprintf (buffer, "%-60s %s", id, name);
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Category Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (buffer);
                bannerBlankBorderTextCen (" ");
                for ( int i = 0; i < 27; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen (
                        "Type another name to change category name... | Press Enter to set by default");
                bannerFullBorder ();
                bannerUserInput ();
                printf ("Default CategoryName: (%s) >>> ", name);
                if ( superscanf (flag) != 0 )
                    categoryUpdateName (strtoul (id, NULL, 10), flag);
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Category Database");
                bannerFullBorder ();
                bannerBlankBorder ();

                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                categorySelectById (strtoul (id, NULL, 10), name);
                sprintf (buffer, "-> %-57s %s", id, name);
                bannerBlankBorderTextLeft (buffer);
                bannerBlankBorder ();
                bannerFullBorder ();
                printf ("::          ID           | Category Name                                                                                                  ::\n");
                bannerFullBorder ();
                for ( int i = 0; i < RecordCount.category; ++i )
                    printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
                for ( int i = 0; i < 25 - RecordCount.category - 3; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Category has been updated");
                bannerBlankBorderTextCen ("Type Next CategoryID to Update Or Type 'B' to Back");
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
            } else {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Category Database");
                bannerFullBorder ();
                bannerBlankBorder ();

                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft ("->");
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextCen ("CategoryID dosen't exist.");
                bannerBlankBorderTextCen ("Type Next CategoryID Or Type 'B' to Back");

                for ( int i = 0; i < 16; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
            }
        }
    }
}
