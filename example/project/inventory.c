// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"

void inventorySwitchHub () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Inventory Management");
    bannerBlankBorder ();
    bannerFullBorder ();
    for ( int i = 0; i < 7; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("What do you want to do ?");
    bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Inventory");
    bannerBlankBorderTextCen ("-------------------");
    bannerBlankBorderTextCen ("1. Check the database");
    bannerBlankBorderTextCen ("2. Add inventory data to the database");
    bannerBlankBorderTextCen ("3. Edit inventory data from the database");
    bannerBlankBorderTextCen ("4. Removing inventory from the database");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Category");
    bannerBlankBorderTextCen ("------------------");
    bannerBlankBorderTextCen ("5. Check the category database");
    bannerBlankBorderTextCen ("6. Add new category to the database");
    bannerBlankBorderTextCen ("7. Edit category from the database");
    for ( int i = 0; i < 7; i++ )
        bannerBlankBorder ();
    if ( errorResponse == 1 )
        bannerBlankBorderTextCen ("Invalid response. Please try again.");
    else
        bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit  |      ALTERNATE RESPONSE      |  Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char userInput;
    scanf (" %c", &userInput);
    switch ( toupper (userInput)) {
        case ('1'):
            inventoryDatabaseInterface ();
            break;
        case ('2'):
            inventoryAdd ();
            break;
        case ('3'):
            inventoryEdit ();
            break;
        case ('4'):
            inventoryRemove ();
            break;
        case ('5'):
            categoryDatabaseInterface ();
            break;
        case ('6'):
            categoryAdd ();
            break;
        case ('7'):
            categoryEdit ();
            break;
        case ('B'):
            switchHub ();
            break;
        case ('Q'):
            terminate ();
        default:
            printf ("Your input is invalid. Please try again...");
            inventorySwitchHub ();
    }
}

int inventorySelectById (char *id, char *name, double *price, double *profit, unsigned int *categoryId,
                         unsigned int *remain) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.inventory;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Inventory[i].id, id) == 0 ) {
            // Return all values back by reference
            strcpy (name, Inventory[i].name);
            *price = Inventory[i].price;
            *profit = Inventory[i].profit;
            *categoryId = Inventory[i].categoryId;
            *remain = Inventory[i].remain;
            return 1;   // Found a record
        }
    }
    return 0;           // Not found the given `id` in the records
}


int inventoryInsert (char *id, char *name, double price, double profit, unsigned int categoryId, unsigned int remain) {
    int tailIndex = RecordCount.inventory;
    // To comfirm that `id` is unique
    for ( int i = 0; i < tailIndex; i++ ) {
        if ( strcmp (Inventory[i].id, id) == 0 )
            return 0;   // Error: Barcode ID already exists
    }
    if ( categoryId >= RecordCount.category )
        return 0;   // Error: CategoryID doesn't exist
    strcpy (Inventory[tailIndex].id, id);
    strcpy (Inventory[tailIndex].name, name);
    Inventory[tailIndex].price = price;
    Inventory[tailIndex].profit = profit;
    Inventory[tailIndex].categoryId = categoryId;
    Inventory[tailIndex].remain = remain;
    RecordCount.inventory++;    // Update the amount of records
    inventoryFileWrite ();       // Save to a Database file
    return 1;                   // Operation Success
}

int inventoryUpdateName (char *id, char *name) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.inventory;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Inventory[i].id, id) == 0 ) {
            strcpy (Inventory[i].name, name);
            inventoryFileWrite ();   // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int inventoryUpdatePrice (char *id, double price) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.inventory;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Inventory[i].id, id) == 0 ) {
            Inventory[i].price = price;
            inventoryFileWrite ();   // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int inventoryUpdateProfit (char *id, double profit) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.inventory;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Inventory[i].id, id) == 0 ) {
            Inventory[i].profit = profit;
            inventoryFileWrite ();   // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int inventoryUpdateCategory (char *id, unsigned int categoryId) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.inventory;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Inventory[i].id, id) == 0 ) {
            Inventory[i].categoryId = categoryId;
            inventoryFileWrite ();   // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int inventoryUpdateRemain (char *id, unsigned int remain) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.inventory;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Inventory[i].id, id) == 0 ) {
            Inventory[i].remain = remain;
            inventoryFileWrite ();   // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int inventoryDelete (char *id) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.inventory;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Inventory[i].id, id) == 0 ) {
            while ( i < numberOfRecords - 1 ) {
                Inventory[i] = Inventory[i + 1];
                i++;
            }
            RecordCount.inventory--;    // Update the amount of records
            inventoryFileWrite ();   // Save to a Database file
            return 1;               // Record successfully deleted
        }
    }
    return 0;   // Not found the given `id` in the records
}

void displayInventory (int page) {
    screenClear ();
    int allPage = (int) ceil (RecordCount.inventory / 32) + 1;
    bannerFullBorder ();
    printf (":: ID             | Name                                               | Price      | Profit     | Category                  | In Stock   ::\n");
    bannerFullBorder ();
    if ( page == allPage ) {
        for ( int i = (page - 1) * 32; i < RecordCount.inventory; ++i ) {
            printf (":: %-14s | %-50s | %10.2lf | %10.2lf | %-25s | %10u ::\n", Inventory[i].id, Inventory[i].name,
                    Inventory[i].price, Inventory[i].profit, Category[Inventory[i].categoryId].name,
                    Inventory[i].remain);
        }
        //display remaining line as bannerBlankBorder()
        for ( int i = 0; i < 32 - (RecordCount.inventory % 32); ++i ) {
            printf ("::                |                                                    |            |            |                           |            ::\n");
        }
    } else {
        for ( int i = (page - 1) * 32; i < page * 32/*(34*page)*/; ++i ) {
            printf (":: %-14s | %-50s | %10.2lf | %10.2lf | %-25s | %10u ::\n", Inventory[i].id, Inventory[i].name,
                    Inventory[i].price, Inventory[i].profit, Category[Inventory[i].categoryId].name,
                    Inventory[i].remain);
        }
    }
    bannerBlankBorderTextCen ("Enter Page/Enter 'B' to back to Inventory Menu");
    printf ("::                                                       <<  <  ( Page %d of %d ) > >>                                                      ::\n",
            page, allPage);
    bannerFullBorder ();
    bannerUserInput ();
}

void inventoryDatabaseInterface () {
    char handling;
    int pageIn = 1, CheckPage;
    displayInventory (1);
    for ( int i = 0; i >= 0; ++i ) {
        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            screenClear ();
            inventorySwitchHub ();
        } else if ( isdigit (handling)) {
            CheckPage = (int) handling - 48;
            if ((CheckPage <= ((int) ceil (RecordCount.inventory / 32) + 1)) && (CheckPage >= 1)) {
                pageIn = (int) handling - 48;
                displayInventory (pageIn);
            } else {
                displayInventory (pageIn);
                printf ("Oops! Page not found, Please enter correct page: ");
            }
        } else {
            displayInventory (pageIn);
            printf ("Oops! Input Error, Please enter correctly: ");
        }
    }
}

void displaySomething ();

void displaySomething () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Insert Inventory");
    bannerFullBorder ();
    for ( int i = 0; i < 36; ++i ) {
        bannerBlankBorder ();
    }
    bannerFullBorder ();
}

void inventoryAdd () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Inventory Database");
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Insert new Inventory");
    bannerFullBorderSection ();
    bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Insert in form");
    bannerBlankBorderTextCen ("Form: ID");
    bannerBlankBorderTextCen ("Name of Inventory");
    bannerBlankBorderTextCen ("Price");
    bannerBlankBorderTextCen ("Profit");
    bannerBlankBorderTextCen ("Category ID(e.g. 0, 1, 2)");
    bannerBlankBorderTextCen ("Number of Inventory(piece)");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Example");
    bannerBlankBorderTextCen ("ID >>> 1234567891012");
    bannerBlankBorderTextCen ("Name >>> Kanomwan");
    bannerBlankBorderTextCen ("Price >>> 10");
    bannerBlankBorderTextCen ("Profit >>> 5");
    bannerBlankBorderTextCen ("Category ID >>> 0");
    bannerBlankBorderTextCen ("Number of piece >>> 50");
    bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Insert Inventory Below");
    for ( int i = 0; i < 11; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char idIN[MAX_LNG_ID], checker, buffer[140], bufferHead[140];
    char nameIN[MAX_LNG_SCREEN];
    double priceIN;
    double profitIN;
    unsigned int categoryIdIN;
    unsigned int remainIN;
    sprintf (bufferHead, "%-20s|%-35s|%-15s|%-15s|%-20s|%-10s", "Inventory ID", "Inventory Name", "Price", "Profit",
             "Category", "In Stock"); //idIN, nameIN, priceIN, profitIN, Category[i].name, remainIN
    while ( 1 ) {
        scanf ("%s", idIN);
        if ( strcmp (idIN, "B") == 0 || strcmp (idIN, "b") == 0 ) {
            inventorySwitchHub ();
            break;
        } else if ( strcmp (idIN, "Q") == 0 || strcmp (idIN, "q") == 0 ) {
            terminate ();
            break;
        } else {
            //------------------After Input ID--------------------
            screenClear ();
            sprintf (buffer, "%-20s->", idIN);
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Inventory Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 27; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please enter The inventory name...");
            bannerFullBorder ();
            bannerUserInput ();
            //---------------------InventoryName--------------------------
            scanf (" %[^\n]", nameIN);
            if ( strlen (nameIN) > 35 )
                sprintf (buffer, "%-20s %-.35s->", idIN, nameIN);
            else
                sprintf (buffer, "%-20s %-35s->", idIN, nameIN);
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Inventory Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 27; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please enter Price...");
            bannerFullBorder ();
            bannerUserInput ();
            //---------------------InventoryPrice--------------------------
            scanf (" %lf", &priceIN);
            if ( strlen (nameIN) > 35 )
                sprintf (buffer, "%-20s %-.35s %15.2lf->", idIN, nameIN, priceIN);
            else
                sprintf (buffer, "%-20s %-35s %15.2lf->", idIN, nameIN, priceIN);
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Inventory Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 27; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please enter Profit...");
            bannerFullBorder ();
            bannerUserInput ();
            //--------------------Profit-------------------------------
            scanf (" %lf", &profitIN);
            if ( strlen (nameIN) > 35 )
                sprintf (buffer, "%-20s %-.35s %15.2lf %15.2lf->", idIN, nameIN, priceIN, profitIN);
            else
                sprintf (buffer, "%-20s %-35s %15.2lf %15.2lf->", idIN, nameIN, priceIN, profitIN);
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Inventory Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            bannerBlankBorder ();
            bannerFullBorder ();
            printf ("::          ID           | Category Name                                                                                                  ::\n");
            bannerFullBorder ();
            for ( int i = 0; i < RecordCount.category; ++i )
                printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
            for ( int i = 0; i < 27 - RecordCount.category - 1 - 3; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please enter Category ID...");
            bannerFullBorder ();

            bannerUserInput ();

            //---------------------CategoryID--------------------------
            scanf (" %u", &categoryIdIN);
            int checkExist = 0;
            for ( int i = 0; i < RecordCount.category; ++i )
                if ( categoryIdIN == Category[i].id )
                    checkExist = 1;
            for ( int i = 0; i >= 0; ++i ) {
                if ( checkExist ) {
                    break;
                } else {
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Inventory Database");
                    bannerFullBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (bufferHead);
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (buffer);
                    bannerBlankBorder ();
                    bannerFullBorder ();
                    printf ("::          ID           | Category Name                                                                                                  ::\n");
                    bannerFullBorder ();
                    for ( int i = 0; i < RecordCount.category; ++i )
                        printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
                    for ( int i = 0; i < (27 - RecordCount.category - 1 - 3); i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("The Category doesn't exist!! Please enter Category ID...");
                    bannerFullBorder ();

                    bannerUserInput ();
                    scanf (" %u", &categoryIdIN);
                    for ( int i = 0; i < RecordCount.category; ++i ) {
                        if ( categoryIdIN == Category[i].id ) {
                            checkExist = 1;
                        }
                    }
                }
            }
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Inventory Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            for ( int i = 0; i < RecordCount.category; ++i ) {
                if ( categoryIdIN == Category[i].id ) {
                    if ( strlen (nameIN) > 35 )
                        sprintf (buffer, "%-20s %-.35s %15.2lf %15.2lf %20s->", idIN, nameIN, priceIN, profitIN,
                                 Category[i].name);
                    else
                        sprintf (buffer, "%-20s %-35s %15.2lf %15.2lf %20s->", idIN, nameIN, priceIN, profitIN,
                                 Category[i].name);
                }
            }
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 27; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please enter Number of this inventory...");
            bannerFullBorder ();
            bannerUserInput ();
            //--------------------N of this inventory--------------------
            scanf (" %u", &remainIN);
            for ( int i = 0; i < RecordCount.category; ++i ) {
                if ( categoryIdIN == Category[i].id ) {
                    if ( strlen (nameIN) > 35 )
                        sprintf (buffer, "%-20s %-.35s %15.2lf %15.2lf %20s %10u", idIN, nameIN, priceIN, profitIN,
                                 Category[i].name, remainIN);
                    else
                        sprintf (buffer, "%-20s %-35s %15.2lf %15.2lf %20s %10u", idIN, nameIN, priceIN, profitIN,
                                 Category[i].name, remainIN);
                }
            }
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Inventory Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 10; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Are you sure to Insert this inventory ?");
            bannerBlankBorderTextCen ("Type 'Y' to Yes || 'N' to No");
            for ( int i = 0; i < 15; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
            bannerFullBorder ();
            bannerUserInput ();
            scanf (" %c", &checker);
            if ( checker == 'y' || checker == 'Y' ) {
                if ( inventoryInsert (idIN, nameIN, priceIN, profitIN, categoryIdIN, remainIN)) {
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Inventory Database");
                    bannerFullBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (bufferHead);
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (buffer);
                    bannerBlankBorder ();
                    bannerBlankBorder ();
                    for ( int i = 0; i < 8; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Insert Success");
                    bannerBlankBorderTextCen ("_____________________");
                    bannerBlankBorderTextCen ("Insert Next Inventory Or Type 'B' to Back");
                    for ( int i = 0; i < 15; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                } else {
                    sprintf (buffer, "ID: %s", idIN);
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Inventory Database");
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Insert Customer");
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Insert not Successful !");
                    bannerBlankBorderTextCen ("Please check your inventory ID");
                    bannerBlankBorder ();
                    bannerBlankBorderTextCen (buffer);
                    bannerBlankBorder ();
                    bannerBlankBorderTextCen ("was a duplicate");
                    bannerBlankBorderTextCen ("_____________________");
                    bannerBlankBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Insert Next Inventory Or Type 'B' to Back");
                    for ( int i = 0; i < 19; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                }
            } else {
                inventoryAdd ();
            }
        }
    }
}

void inventoryEdit () {
    char bufferHead[140];
    sprintf (bufferHead, "%-20s|%-30s|%-15s|%-15s|%-30s|%-10s", "ID", "Name", "Price", "Profit", "Category",
             "In Stock");
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Inventory Database");
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft (bufferHead);
    bannerFullBorderSection ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft ("->");
    for ( int i = 0; i < 10; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type InventoryID");
    for ( int i = 0; i < 17; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char id[MAX_LNG_ID], name[MAX_LNG_TEXT], buffer[140], flag[MAX_LNG_TEXT], categoryName[MAX_LNG_TEXT], flagCategory[MAX_LNG_TEXT];
    double price, profit;
    unsigned int remain, category;
    while ( 1 ) {
        scanf ("%s", id);
        if ( strcmp (id, "B") == 0 || strcmp (id, "b") == 0 ) {
            inventorySwitchHub ();
        } else if ( strcmp (id, "Q") == 0 || strcmp (id, "q") == 0 ) {
            terminate ();
        } else {
            if ( inventorySelectById (id, name, &price, &profit, &category, &remain)) {
                categorySelectById (category, categoryName);
                if ( strlen (name) > 30 )
                    sprintf (buffer, "%-20s %-.30s %-15.2lf %-15.2lf %-30s %-10u", id, name, price, profit,
                             categoryName, remain);
                else
                    sprintf (buffer, "%-20s %-30s %-15.2lf %-15.2lf %-30s %-10u", id, name, price, profit, categoryName,
                             remain);
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Inventory Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (buffer);
                bannerBlankBorderTextCen (" ");
                bannerBlankBorder ();
                bannerFullBorder ();
                printf ("::          ID           | Category Name                                                                                                  ::\n");
                bannerFullBorder ();
                for ( int i = 0; i < RecordCount.category; ++i )
                    printf ("::          %2u           | %-110s ::\n", Category[i].id, Category[i].name);
                for ( int i = 0; i < (28 - RecordCount.category - 5); i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen (
                        "Type another name to change category name... | Press Enter to set by default");
                bannerFullBorder ();
                bannerUserInput ();
                printf ("Default Name: (%s) >>> ", name);
                if ( superscanf (flag) != 0 )
                    inventoryUpdateName (id, flag);
                printf ("Default Price: (%.2lf) >>> ", price);
                if ( superscanf (flag) != 0 )
                    inventoryUpdatePrice (id, atof (flag));
                printf ("Default Profit: (%.2lf) >>> ", profit);
                if ( superscanf (flag) != 0 )
                    inventoryUpdateProfit (id, atof (flag));
                printf ("Default Category: (%u) >>> ", category);
                if ( superscanf (flag) != 0 ) {
                    strcpy (flagCategory, flag);
                    if ( categorySelectById (strtoul (flag, NULL, 10), categoryName))
                        inventoryUpdateCategory (id, strtoul (flag, NULL, 10));
                }
                printf ("Default Remain: (%u) >>> ", remain);
                if ( superscanf (flag) != 0 )
                    inventoryUpdateRemain (id, strtoul (flag, NULL, 10));
                if ( categorySelectById (strtoul (flagCategory, NULL, 10), categoryName) == 0 ) {
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Inventory Database");
                    bannerFullBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (bufferHead);
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    if ( strlen (name) > 30 )
                        sprintf (buffer, "%-20s %-.30s %-15.2lf %-15.2lf ->%-30s %-10u", id, name, price, profit,
                                 "Doesn't Exist !", remain);
                    else
                        sprintf (buffer, "%-20s %-30s %-15.2lf %-15.2lf ->%-30s %-10u", id, name, price, profit,
                                 "Doesn't Exist !", remain);
                    bannerBlankBorderTextLeft (buffer);
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft ("");
                    for ( int i = 0; i < 10; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Category ID doesn't exist");
                    bannerBlankBorderTextCen ("Please re-type Inventory ID | Type 'B' to back");
                    for ( int i = 0; i < 14; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                } else {
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Inventory Database");
                    bannerFullBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (bufferHead);
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    inventorySelectById (id, name, &price, &profit, &category, &remain);
                    categorySelectById (category, categoryName);
                    if ( strlen (name) > 30 )
                        sprintf (buffer, "%-20s %-.30s %-15.2lf %-15.2lf %-30s %-10u", id, name, price, profit,
                                 categoryName, remain);
                    else
                        sprintf (buffer, "%-20s %-30s %-15.2lf %-15.2lf %-30s %-10u", id, name, price, profit,
                                 categoryName, remain);
                    bannerBlankBorderTextLeft (buffer);
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft ("->");
                    for ( int i = 0; i < 10; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Inventoy has been updated");
                    bannerBlankBorderTextCen ("Type Next InventoyID to Update Or Type 'B' to Back");
                    for ( int i = 0; i < 14; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                }
            } else {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Inventory Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft ("->");
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextCen ("InventoryID dosen't exist.");
                bannerBlankBorderTextCen ("Type Next InventoryID Or Type 'B' to Back");
                for ( int i = 0; i < 15; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
            }
        }
    }
}

void inventoryRemove () {
    screenClear ();
    char idIN[MAX_LNG_ID];
    char handling;
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Removing Inventory");
    bannerFullBorder ();
    for ( int i = 0; i < 33; ++i )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    //Process
    for ( int i = 0; i >= 0; ++i ) {
        printf ("\n");
        printf ("Enter the inventory ID to delete >>> ");
        scanf ("%s", idIN);
        char nameMEM[MAX_LNG_TEXT];
        double priceMEM, profitMEM;
        unsigned int categoryIdMEM, remainMEM;
        inventorySelectById (idIN, nameMEM, &priceMEM, &profitMEM, &categoryIdMEM, &remainMEM);
        if ((strcmp (idIN, "B") == 0) || (strcmp (idIN, "b") == 0))
            inventorySwitchHub ();
        else if ((strcmp (idIN, "Q") == 0) || (strcmp (idIN, "q") == 0))
            terminate ();
        else {
            if ( inventoryDelete (idIN)) {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Removing Inventory");
                bannerFullBorder ();
                for ( int i = 0; i < 14; ++i )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen (idIN);
                bannerBlankBorderTextCen (nameMEM);
                for ( int i = 0; i < RecordCount.category; ++i ) {
                    if ( categoryIdMEM == Category[i].id ) {
                        bannerBlankBorderTextCen (Category[i].name);
                    }
                }
                bannerBlankBorder ();
                bannerBlankBorderTextCen ("Success!!! The inventory has been deleted.");
                for ( int i = 0; i < 14; ++i )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
            } else {
                screenClear ();
                bannerFullBorder ();
                for ( int i = 0; i < 17; ++i )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Error!!! The inventory ID does not exist.");
                for ( int i = 0; i < 17; ++i )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
            }
        }
    }
}
