# ConferenceCenter

## Installing and running locally
- Clone the repository.
- Launch Google App Engine Launcher.
- Once open, add this project to the Launcher by:
  1. Select `File` > `Add Existing Application`.
  2. Point to where you cloned your repository.
  3. If you want to use specific ports, add those here.
  4. Select `Add`.
- Now make sure that you have the project selected, then click `Run`.
- In your browser, go to localhost:<the port you chose in step 3>.
- The API Explorer can be accessed by appending `_ah/api/explorer` to the URL, e.g. `localhost:8080/_ah/api/explorer`.

## Entities
#### Session
A session entity represents a conference event and can be of several types. A session must be a child of a conference since you can't have independent sessions outside of the conferences. This is done by creating a relationship between sessions and conferences by passing the required key to `parentConference`, and can only be done by the creator of the conference. Currently there is no limit on how many sessions an conference can host.

#### Speaker
`Speakers` are associated with entities session and are, just as `Sessions`, a separate entity. This design choice was made to make the code more readable and consistent, both in how it's structured but also how the API calls are being made. Unlike `Sessions`, `Speakers` only required field is `name`.   

## Additional queries
#### getSessionsByDate
`getSessionsByDate` returns all sessions for a conference on a given date. If participants are only able to attend a conference on a specific date, one would want to filter by date to see what options there are.

#### getSpeakers
`getSpeakers` returns all the speakers for the given conference. This gives an overview of who is going to speaking at the conference.

## Solve the following query related problem
> Let’s say that you don't like workshops and you don't like sessions after 7 pm. How would you handle a query for all non-workshop sessions before 7 pm? What is the problem for implementing this query? What ways to solve it did you think of?

The problem with this query is that it can't be created as a "single" query since there are two properties that needs inequality filters. What one should do is to create two keys to query against (one for the type of session and one for time), which after you could diff both entity keys to find which ones meets the criteria for both queries.
